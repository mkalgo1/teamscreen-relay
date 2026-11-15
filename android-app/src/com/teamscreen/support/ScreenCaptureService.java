package com.teamscreen.support;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.IBinder;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.WindowManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

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

    private volatile boolean mRunning = false;
    private volatile boolean mStreamRequested = true;
    private Thread mCaptureThread;
    private Thread mHeartbeatThread;
    private Thread mInputReceiverThread;

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
            payload.put("status", "Streaming");
            payload.put("screenResolution", mWidth + "x" + mHeight);

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
