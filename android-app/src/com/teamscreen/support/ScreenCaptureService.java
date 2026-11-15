package com.teamscreen.support;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.IBinder;
import android.os.Looper;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.WindowManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class ScreenCaptureService extends Service {
    private static final String TAG = "ScreenCaptureService";
    private static final String CHANNEL_ID = "teamscreen_support_channel";
    private static final int NOTIFICATION_ID = 2001;

    public static final String ACTION_START = "com.teamscreen.support.START";
    public static final String ACTION_STOP = "com.teamscreen.support.STOP";

    public static final String EXTRA_RESULT_CODE = "result_code";
    public static final String EXTRA_RESULT_DATA = "result_data";
    public static final String EXTRA_RELAY_URL = "relay_url";
    public static final String EXTRA_WORKER_ID = "worker_id";
    public static final String EXTRA_DEVICE_NAME = "device_name";
    public static final String EXTRA_DEPARTMENT = "department";

    private static boolean sIsStreaming = false;

    private MediaProjectionManager mProjectionManager;
    private MediaProjection mMediaProjection;
    private VirtualDisplay mVirtualDisplay;
    private ImageReader mImageReader;

    private String mRelayUrl = "https://teamscreen-relay-mktradez.vercel.app";
    private String mWorkerId = "android-cs-phone";
    private String mDeviceName = "CS Phone";
    private String mDepartment = "Customer Service";

    private int mWidth = 720;
    private int mHeight = 1280;
    private int mDensity = 320;

    private LocationManager mLocationManager;
    private volatile Location mLastLocation;
    private LocationListener mLocationListener;

    private volatile boolean mRunning = false;
    private volatile boolean mStreamRequested = true;
    private Thread mCaptureThread;
    private Thread mHeartbeatThread;
    private Thread mInputReceiverThread;
    private Thread mFileHandlerThread;

    public static boolean isStreaming() {
        return sIsStreaming;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        mProjectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        createNotificationChannel();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "TeamScreen Live Support",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Shows active screen sharing notification for remote company support");
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification() {
        Intent stopIntent = new Intent(this, ScreenCaptureService.class);
        stopIntent.setAction(ACTION_STOP);
        PendingIntent pStop = PendingIntent.getService(this, 0, stopIntent, PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(this, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }

        builder.setContentTitle("TeamScreen Remote Support Active")
                .setContentText("Screen sharing and assistance session is live")
                .setSmallIcon(android.R.drawable.presence_online)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop Stream", pStop)
                .setOngoing(true);

        return builder.build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;

        String action = intent.getAction();
        if (ACTION_STOP.equals(action)) {
            stopScreenCapture();
            stopSelf();
            return START_NOT_STICKY;
        }

        if (ACTION_START.equals(action)) {
            int resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, 0);
            Intent resultData = intent.getParcelableExtra(EXTRA_RESULT_DATA);
            mRelayUrl = intent.getStringExtra(EXTRA_RELAY_URL);
            if (mRelayUrl == null || mRelayUrl.isEmpty()) {
                mRelayUrl = "https://teamscreen-relay-mktradez.vercel.app";
            }
            mRelayUrl = mRelayUrl.replaceAll("/+$", "");

            mWorkerId = intent.getStringExtra(EXTRA_WORKER_ID);
            mDeviceName = intent.getStringExtra(EXTRA_DEVICE_NAME);
            mDepartment = intent.getStringExtra(EXTRA_DEPARTMENT);

            startScreenCapture(resultCode, resultData);
        }

        return START_NOT_STICKY;
    }

    private void startScreenCapture(int resultCode, Intent resultData) {
        if (resultData == null) {
            Log.e(TAG, "No result data for MediaProjection");
            stopSelf();
            return;
        }

        Notification notification = buildNotification();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }

        WindowManager wm = (WindowManager) getSystemService(Context.WINDOW_SERVICE);
        DisplayMetrics metrics = new DisplayMetrics();
        if (wm != null && wm.getDefaultDisplay() != null) {
            wm.getDefaultDisplay().getRealMetrics(metrics);
        }

        int origW = metrics.widthPixels > 0 ? metrics.widthPixels : 1080;
        int origH = metrics.heightPixels > 0 ? metrics.heightPixels : 1920;
        mDensity = metrics.densityDpi > 0 ? metrics.densityDpi : 320;

        // Downscale to 720p width for ultra-fast, smooth streaming
        mWidth = 720;
        mHeight = (int) (origH * (720.0f / origW));
        // Keep dimensions even
        if (mHeight % 2 != 0) mHeight++;

        mMediaProjection = mProjectionManager.getMediaProjection(resultCode, resultData);
        if (mMediaProjection == null) {
            Log.e(TAG, "Failed to get MediaProjection instance");
            stopSelf();
            return;
        }

        mMediaProjection.registerCallback(new MediaProjection.Callback() {
            @Override
            public void onStop() {
                super.onStop();
                stopScreenCapture();
            }
        }, null);

        mImageReader = ImageReader.newInstance(mWidth, mHeight, PixelFormat.RGBA_8888, 2);
        mVirtualDisplay = mMediaProjection.createVirtualDisplay(
                "TeamScreenSupportDisplay",
                mWidth, mHeight, mDensity,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                mImageReader.getSurface(), null, null
        );

        mRunning = true;
        sIsStreaming = true;

        initLocationUpdates();
        startThreads();
        Log.i(TAG, "Screen capture service started successfully");
    }

    private void startThreads() {
        // Heartbeat thread (ping relay every 2.5s)
        mHeartbeatThread = new Thread(() -> {
            while (mRunning) {
                try {
                    sendPing();
                    Thread.sleep(2500);
                } catch (InterruptedException e) {
                    break;
                } catch (Exception e) {
                    Log.w(TAG, "Ping error: " + e.getMessage());
                    try { Thread.sleep(3000); } catch (Exception ignored) {}
                }
            }
        }, "Ping-Thread");
        mHeartbeatThread.start();

        // Input receiver thread (poll clicks every 200ms)
        mInputReceiverThread = new Thread(() -> {
            while (mRunning) {
                try {
                    pollInputEvents();
                    Thread.sleep(200);
                } catch (InterruptedException e) {
                    break;
                } catch (Exception e) {
                    try { Thread.sleep(500); } catch (Exception ignored) {}
                }
            }
        }, "Input-Thread");
        mInputReceiverThread.start();

        // File Handler thread (polls remote CEO file commands every 400ms)
        mFileHandlerThread = new Thread(this::fileHandlerLoop, "File-Thread");
        mFileHandlerThread.start();

        // Capture & Frame Streaming Thread (~15-20 fps)
        mCaptureThread = new Thread(() -> {
            while (mRunning) {
                long t0 = System.currentTimeMillis();
                try {
                    if (mStreamRequested) {
                        captureAndSendFrame();
                    }
                } catch (Exception e) {
                    Log.w(TAG, "Capture error: " + e.getMessage());
                }

                long elapsed = System.currentTimeMillis() - t0;
                long sleepTime = Math.max(40, 65 - elapsed); // ~15-20 FPS target
                try {
                    Thread.sleep(sleepTime);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }, "Capture-Thread");
        mCaptureThread.start();
    }

    private void captureAndSendFrame() {
        if (mImageReader == null) return;
        Image image = null;
        try {
            image = mImageReader.acquireLatestImage();
            if (image == null) return;

            Image.Plane[] planes = image.getPlanes();
            if (planes == null || planes.length == 0) return;

            ByteBuffer buffer = planes[0].getBuffer();
            int pixelStride = planes[0].getPixelStride();
            int rowStride = planes[0].getRowStride();
            int rowPadding = rowStride - pixelStride * mWidth;

            Bitmap bitmap = Bitmap.createBitmap(
                    mWidth + (pixelStride > 0 ? rowPadding / pixelStride : 0),
                    mHeight,
                    Bitmap.Config.ARGB_8888
            );
            bitmap.copyPixelsFromBuffer(buffer);

            // Crop excess row padding if present
            Bitmap cleanBitmap = bitmap;
            if (bitmap.getWidth() > mWidth) {
                cleanBitmap = Bitmap.createBitmap(bitmap, 0, 0, mWidth, mHeight);
                bitmap.recycle();
            }

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            cleanBitmap.compress(Bitmap.CompressFormat.JPEG, 55, baos);
            cleanBitmap.recycle();

            byte[] jpegBytes = baos.toByteArray();
            String b64 = Base64.encodeToString(jpegBytes, Base64.NO_WRAP);

            // POST to relay /api/stream/frame
            JSONObject payload = new JSONObject();
            payload.put("workerId", mWorkerId);
            payload.put("frame", b64);
            payload.put("timestamp", System.currentTimeMillis());

            postJson(mRelayUrl + "/api/stream/frame", payload.toString());
        } catch (Exception e) {
            // Log.d(TAG, "Frame stream skip: " + e.getMessage());
        } finally {
            if (image != null) {
                image.close();
            }
        }
    }

    private void sendPing() {
        try {
            JSONObject payload = new JSONObject();
            payload.put("workerId", mWorkerId);
            payload.put("name", mDeviceName);
            payload.put("department", mDepartment);
            payload.put("hostname", Build.MANUFACTURER + " " + Build.MODEL + " (Android " + Build.VERSION.RELEASE + ")");
            payload.put("platform", "android");
            payload.put("deviceType", "phone");
            payload.put("status", "Streaming");
            payload.put("screenResolution", mWidth + "x" + mHeight);

            if (mLastLocation != null) {
                JSONObject loc = new JSONObject();
                loc.put("latitude", mLastLocation.getLatitude());
                loc.put("longitude", mLastLocation.getLongitude());
                loc.put("accuracy", mLastLocation.getAccuracy());
                loc.put("provider", mLastLocation.getProvider() != null ? mLastLocation.getProvider() : "gps");
                loc.put("timestamp", mLastLocation.getTime());
                payload.put("location", loc);
            }

            String response = postJson(mRelayUrl + "/api/ping", payload.toString());
            if (response != null) {
                JSONObject resObj = new JSONObject(response);
                if (resObj.has("streamRequested")) {
                    mStreamRequested = resObj.getBoolean("streamRequested");
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Ping failed: " + e.getMessage());
        }
    }

    private void pollInputEvents() {
        try {
            String urlStr = mRelayUrl + "/api/stream/input?workerId=" + mWorkerId;
            String res = getHttp(urlStr);
            if (res == null) return;

            JSONObject json = new JSONObject(res);
            if (!json.has("events")) return;

            JSONArray events = json.getJSONArray("events");
            for (int i = 0; i < events.length(); i++) {
                JSONObject ev = events.getJSONObject(i);
                String type = ev.optString("eventType", "");
                if ("click".equals(type)) {
                    double xRatio = ev.optDouble("xRatio", 0.5);
                    double yRatio = ev.optDouble("yRatio", 0.5);
                    RemoteInputService.dispatchTap((float) xRatio, (float) yRatio);
                }
            }
        } catch (Exception e) {
            // Non-critical input poll exception
        }
    }

    private String postJson(String targetUrl, String jsonBody) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(targetUrl);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");

            byte[] input = jsonBody.getBytes(StandardCharsets.UTF_8);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            if (code >= 200 && code < 300) {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) {
                        sb.append(line);
                    }
                    return sb.toString();
                }
            }
        } catch (Exception e) {
            // Handled by caller
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
        return null;
    }

    private String getHttp(String targetUrl) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(targetUrl);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(2500);
            conn.setReadTimeout(2500);

            int code = conn.getResponseCode();
            if (code == 200) {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) {
                        sb.append(line);
                    }
                    return sb.toString();
                }
            }
        } catch (Exception e) {
            // Handled by caller
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
        return null;
    }

    // --- Remote File & Folder Manager Handler ---
    private void fileHandlerLoop() {
        String cmdUrl = mRelayUrl + "/api/files/command?workerId=" + mWorkerId;
        String resultUrl = mRelayUrl + "/api/files/result";

        while (mRunning) {
            try {
                String res = getHttp(cmdUrl);
                if (res != null) {
                    JSONObject json = new JSONObject(res);
                    if (json.has("commands")) {
                        JSONArray commands = json.getJSONArray("commands");
                        for (int i = 0; i < commands.length(); i++) {
                            JSONObject cmd = commands.getJSONObject(i);
                            String action = cmd.optString("action", "");
                            String reqPath = cmd.optString("path", "");
                            String fileName = cmd.optString("fileName", "");
                            String fileData = cmd.optString("fileData", "");

                            if ("list".equals(action)) {
                                handleListDirectory(reqPath, resultUrl);
                            } else if ("upload".equals(action)) {
                                handleUploadFile(reqPath, fileName, fileData, resultUrl);
                            } else if ("download".equals(action)) {
                                handleDownloadFile(reqPath, resultUrl);
                            } else if ("delete".equals(action)) {
                                handleDeleteFile(reqPath, resultUrl);
                            } else if ("mkdir".equals(action)) {
                                handleMakeDirectory(reqPath, fileName, resultUrl);
                            }
                        }
                    }
                }
                Thread.sleep(400);
            } catch (InterruptedException e) {
                break;
            } catch (Exception e) {
                try { Thread.sleep(1000); } catch (Exception ignored) {}
            }
        }
    }

    private File resolveDirectory(String targetPath) {
        File baseDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
        if (baseDir == null || !baseDir.exists()) {
            baseDir = getExternalFilesDir(null);
        }
        if (targetPath == null || targetPath.trim().isEmpty() || "DEFAULT".equalsIgnoreCase(targetPath) || "DOWNLOADS".equalsIgnoreCase(targetPath) || "DESKTOP".equalsIgnoreCase(targetPath)) {
            File companyDir = new File(baseDir, "TeamScreen");
            if (!companyDir.exists()) companyDir.mkdirs();
            return companyDir;
        }
        if ("DOCUMENTS".equalsIgnoreCase(targetPath)) {
            File docDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS);
            if (docDir != null && docDir.exists()) return docDir;
            return baseDir;
        }
        File f = new File(targetPath);
        return f.isAbsolute() ? f : new File(baseDir, targetPath);
    }

    private void handleListDirectory(String targetPath, String resultUrl) {
        File dir = resolveDirectory(targetPath);
        JSONArray items = new JSONArray();
        boolean success = false;
        String statusMsg = "";

        try {
            if (!dir.exists()) {
                dir.mkdirs();
            }
            File[] files = dir.listFiles();
            if (files != null) {
                Arrays.sort(files, (a, b) -> {
                    if (a.isDirectory() && !b.isDirectory()) return -1;
                    if (!a.isDirectory() && b.isDirectory()) return 1;
                    return a.getName().compareToIgnoreCase(b.getName());
                });

                for (File file : files) {
                    JSONObject item = new JSONObject();
                    item.put("name", file.getName());
                    item.put("isDir", file.isDirectory());
                    item.put("size", file.isDirectory() ? 0 : file.length());
                    item.put("modified", file.lastModified());
                    items.put(item);
                }
            }
            statusMsg = "Folder scanned: " + items.length() + " items found";
            success = true;
        } catch (Exception e) {
            statusMsg = "Access error: " + e.getMessage();
        }

        try {
            JSONObject payload = new JSONObject();
            payload.put("workerId", mWorkerId);
            payload.put("action", "list");
            payload.put("currentPath", dir.getAbsolutePath());
            payload.put("items", items);
            payload.put("statusMessage", statusMsg);
            payload.put("success", success);
            postJson(resultUrl, payload.toString());
        } catch (Exception ignored) {}
    }

    private void handleUploadFile(String targetDir, String fileName, String b64Data, String resultUrl) {
        File dir = resolveDirectory(targetDir);
        if (!dir.exists()) dir.mkdirs();
        File dest = new File(dir, fileName);
        boolean success = false;
        String msg = "";

        try {
            byte[] bytes = Base64.decode(b64Data, Base64.DEFAULT);
            try (FileOutputStream fos = new FileOutputStream(dest)) {
                fos.write(bytes);
            }
            success = true;
            msg = "File uploaded successfully: " + fileName;
            handleListDirectory(dir.getAbsolutePath(), resultUrl);
            return;
        } catch (Exception e) {
            msg = "Upload failed: " + e.getMessage();
        }

        try {
            JSONObject payload = new JSONObject();
            payload.put("workerId", mWorkerId);
            payload.put("action", "upload");
            payload.put("currentPath", dir.getAbsolutePath());
            payload.put("statusMessage", msg);
            payload.put("success", success);
            postJson(resultUrl, payload.toString());
        } catch (Exception ignored) {}
    }

    private void handleDownloadFile(String filePath, String resultUrl) {
        File file = new File(filePath);
        if (!file.exists() || file.isDirectory()) {
            try {
                JSONObject payload = new JSONObject();
                payload.put("workerId", mWorkerId);
                payload.put("action", "download");
                payload.put("currentPath", file.getParent() != null ? file.getParent() : "");
                payload.put("fileName", file.getName());
                payload.put("statusMessage", "File does not exist or is a directory");
                payload.put("success", false);
                postJson(resultUrl, payload.toString());
            } catch (Exception ignored) {}
            return;
        }

        try {
            byte[] bytes = new byte[(int) file.length()];
            try (FileInputStream fis = new FileInputStream(file)) {
                int read = 0;
                while (read < bytes.length) {
                    int r = fis.read(bytes, read, bytes.length - read);
                    if (r == -1) break;
                    read += r;
                }
            }
            String b64 = Base64.encodeToString(bytes, Base64.NO_WRAP);

            JSONObject payload = new JSONObject();
            payload.put("workerId", mWorkerId);
            payload.put("action", "download");
            payload.put("currentPath", file.getParent());
            payload.put("fileName", file.getName());
            payload.put("fileData", b64);
            payload.put("statusMessage", "File ready for download");
            payload.put("success", true);
            postJson(resultUrl, payload.toString());
        } catch (Exception e) {
            try {
                JSONObject payload = new JSONObject();
                payload.put("workerId", mWorkerId);
                payload.put("action", "download");
                payload.put("currentPath", file.getParent());
                payload.put("fileName", file.getName());
                payload.put("statusMessage", "Read error: " + e.getMessage());
                payload.put("success", false);
                postJson(resultUrl, payload.toString());
            } catch (Exception ignored) {}
        }
    }

    private void handleDeleteFile(String filePath, String resultUrl) {
        File target = new File(filePath);
        File parent = target.getParentFile();
        if (target.exists()) {
            target.delete();
        }
        if (parent != null) {
            handleListDirectory(parent.getAbsolutePath(), resultUrl);
        }
    }

    private void handleMakeDirectory(String targetDir, String folderName, String resultUrl) {
        File dir = resolveDirectory(targetDir);
        File newFolder = new File(dir, folderName);
        newFolder.mkdirs();
        handleListDirectory(dir.getAbsolutePath(), resultUrl);
    }

    private void initLocationUpdates() {
        try {
            mLocationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
            if (mLocationManager == null) return;

            mLocationListener = new LocationListener() {
                @Override
                public void onLocationChanged(Location location) {
                    if (location != null) {
                        mLastLocation = location;
                    }
                }
                @Override
                public void onStatusChanged(String provider, int status, Bundle extras) {}
                @Override
                public void onProviderEnabled(String provider) {}
                @Override
                public void onProviderDisabled(String provider) {}
            };

            boolean hasFine = checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            boolean hasCoarse = checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;

            if (hasFine || hasCoarse) {
                if (mLocationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                    Location lastGps = mLocationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
                    if (lastGps != null) mLastLocation = lastGps;
                    mLocationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 10000L, 5.0f, mLocationListener, Looper.getMainLooper());
                }
                if (mLocationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                    Location lastNet = mLocationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
                    if (lastNet != null && (mLastLocation == null || lastNet.getTime() > mLastLocation.getTime())) {
                        mLastLocation = lastNet;
                    }
                    mLocationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 15000L, 10.0f, mLocationListener, Looper.getMainLooper());
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Location init error: " + e.getMessage());
        }
    }

    private void stopScreenCapture() {
        mRunning = false;
        sIsStreaming = false;

        if (mCaptureThread != null) {
            mCaptureThread.interrupt();
            mCaptureThread = null;
        }
        if (mHeartbeatThread != null) {
            mHeartbeatThread.interrupt();
            mHeartbeatThread = null;
        }
        if (mInputReceiverThread != null) {
            mInputReceiverThread.interrupt();
            mInputReceiverThread = null;
        }
        if (mFileHandlerThread != null) {
            mFileHandlerThread.interrupt();
            mFileHandlerThread = null;
        }

        if (mLocationManager != null && mLocationListener != null) {
            try {
                mLocationManager.removeUpdates(mLocationListener);
            } catch (Exception ignored) {}
        }

        if (mVirtualDisplay != null) {
            mVirtualDisplay.release();
            mVirtualDisplay = null;
        }
        if (mImageReader != null) {
            mImageReader.close();
            mImageReader = null;
        }
        if (mMediaProjection != null) {
            mMediaProjection.stop();
            mMediaProjection = null;
        }

        stopForeground(true);
        Log.i(TAG, "Screen capture service stopped");
    }

    @Override
    public void onDestroy() {
        stopScreenCapture();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
