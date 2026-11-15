package com.teamscreen.support;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.util.UUID;

public class MainActivity extends Activity {
    private static final String TAG = "MainActivity";
    private static final int REQUEST_MEDIA_PROJECTION = 101;
    private static final int REQUEST_NOTIF_PERMISSION = 102;
    private static final String PREFS_NAME = "TeamScreenPrefs";

    private EditText mEditRelayUrl;
    private EditText mEditDeviceName;
    private EditText mEditDepartment;
    private TextView mTxtAccessibilityStatus;
    private Button mBtnEnableAccessibility;
    private TextView mTxtStreamStatus;
    private Button mBtnToggleStream;
    private TextView mTxtLogs;

    private MediaProjectionManager mProjectionManager;
    private String mWorkerId;
    private Handler mHandler;
    private Runnable mStatusChecker;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        mProjectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
        mHandler = new Handler(Looper.getMainLooper());

        initViews();
        loadSavedConfig();
        requestNotificationPermission();

        mStatusChecker = new Runnable() {
            @Override
            public void run() {
                updateUIState();
                mHandler.postDelayed(this, 1000);
            }
        };
    }

    private void initViews() {
        mEditRelayUrl = findViewById(R.id.editRelayUrl);
        mEditDeviceName = findViewById(R.id.editDeviceName);
        mEditDepartment = findViewById(R.id.editDepartment);
        mTxtAccessibilityStatus = findViewById(R.id.txtAccessibilityStatus);
        mBtnEnableAccessibility = findViewById(R.id.btnEnableAccessibility);
        mTxtStreamStatus = findViewById(R.id.txtStreamStatus);
        mBtnToggleStream = findViewById(R.id.btnToggleStream);
        mTxtLogs = findViewById(R.id.txtLogs);

        mBtnEnableAccessibility.setOnClickListener(v -> {
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            startActivity(intent);
            Toast.makeText(this, "Enable 'TeamScreen Remote Control' in list", Toast.LENGTH_LONG).show();
            log("Opening Accessibility Settings...");
        });

        mBtnToggleStream.setOnClickListener(v -> {
            if (ScreenCaptureService.isStreaming()) {
                stopStreamService();
            } else {
                saveConfig();
                startMediaProjectionRequest();
            }
        });
    }

    private void loadSavedConfig() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        mWorkerId = prefs.getString("worker_id", null);
        if (mWorkerId == null) {
            String shortId = UUID.randomUUID().toString().substring(0, 8);
            mWorkerId = "android-cs-" + shortId;
            prefs.edit().putString("worker_id", mWorkerId).apply();
        }

        String defaultName = "CS Phone (" + Build.MODEL + ")";
        String savedRelay = prefs.getString("relay_url", "https://teamscreen-relay-mktradez.vercel.app");
        String savedName = prefs.getString("device_name", defaultName);
        String savedDept = prefs.getString("department", "Customer Service");

        mEditRelayUrl.setText(savedRelay);
        mEditDeviceName.setText(savedName);
        mEditDepartment.setText(savedDept);

        log("Device Worker ID: " + mWorkerId);
        log("Relay: " + savedRelay);
    }

    private void saveConfig() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit()
                .putString("relay_url", mEditRelayUrl.getText().toString().trim())
                .putString("device_name", mEditDeviceName.getText().toString().trim())
                .putString("department", mEditDepartment.getText().toString().trim())
                .apply();
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            if (checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, REQUEST_NOTIF_PERMISSION);
            }
        }
    }

    private boolean isAccessibilityActive() {
        if (RemoteInputService.isServiceActive()) return true;
        try {
            int accessibilityEnabled = Settings.Secure.getInt(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED);
            if (accessibilityEnabled == 1) {
                String settingValue = Settings.Secure.getString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
                if (settingValue != null) {
                    return settingValue.contains(getPackageName());
                }
            }
        } catch (Exception ignored) {}
        return false;
    }

    private void updateUIState() {
        boolean accessActive = isAccessibilityActive();
        if (accessActive) {
            mTxtAccessibilityStatus.setText("Status: Active (Remote Clicks Ready)");
            mTxtAccessibilityStatus.setTextColor(0xFF22C55E);
            mBtnEnableAccessibility.setText("Accessibility Enabled");
            mBtnEnableAccessibility.setEnabled(false);
        } else {
            mTxtAccessibilityStatus.setText("Status: Disabled (Click below to grant)");
            mTxtAccessibilityStatus.setTextColor(0xFFEF4444);
            mBtnEnableAccessibility.setText("Enable Remote Click Service");
            mBtnEnableAccessibility.setEnabled(true);
        }

        boolean streaming = ScreenCaptureService.isStreaming();
        if (streaming) {
            mTxtStreamStatus.setText("Status: Streaming Live to CEO Admin");
            mTxtStreamStatus.setTextColor(0xFF22C55E);
            mBtnToggleStream.setText("Stop Support Session");
            mBtnToggleStream.setBackgroundColor(0xFFEF4444);
        } else {
            mTxtStreamStatus.setText("Status: Disconnected / Ready");
            mTxtStreamStatus.setTextColor(0xFF94A3B8);
            mBtnToggleStream.setText("Start Support Session");
            mBtnToggleStream.setBackgroundColor(0xFF38BDF8);
        }
    }

    private void startMediaProjectionRequest() {
        if (mProjectionManager != null) {
            log("Requesting screen capture permission...");
            startActivityForResult(mProjectionManager.createScreenCaptureIntent(), REQUEST_MEDIA_PROJECTION);
        } else {
            log("Error: MediaProjectionManager is not available.");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_MEDIA_PROJECTION) {
            if (resultCode == RESULT_OK && data != null) {
                log("Screen capture permission granted! Starting service...");
                startStreamService(resultCode, data);
            } else {
                log("Screen capture permission was declined.");
                Toast.makeText(this, "Screen capture permission is required to stream", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void startStreamService(int resultCode, Intent data) {
        Intent serviceIntent = new Intent(this, ScreenCaptureService.class);
        serviceIntent.setAction(ScreenCaptureService.ACTION_START);
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_RESULT_CODE, resultCode);
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_RESULT_DATA, data);
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_RELAY_URL, mEditRelayUrl.getText().toString().trim());
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_WORKER_ID, mWorkerId);
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_DEVICE_NAME, mEditDeviceName.getText().toString().trim());
        serviceIntent.putExtra(ScreenCaptureService.EXTRA_DEPARTMENT, mEditDepartment.getText().toString().trim());

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }
        log("Streaming service started. Registered as " + mWorkerId);
    }

    private void stopStreamService() {
        Intent serviceIntent = new Intent(this, ScreenCaptureService.class);
        serviceIntent.setAction(ScreenCaptureService.ACTION_STOP);
        startService(serviceIntent);
        log("Streaming service stopped.");
    }

    private void log(String msg) {
        String current = mTxtLogs.getText().toString();
        String newLog = "[" + android.text.format.DateFormat.format("HH:mm:ss", System.currentTimeMillis()) + "] " + msg + "\n" + current;
        if (newLog.length() > 2000) {
            newLog = newLog.substring(0, 2000);
        }
        mTxtLogs.setText(newLog);
    }

    @Override
    protected void onResume() {
        super.onResume();
        mHandler.post(mStatusChecker);
    }

    @Override
    protected void onPause() {
        mHandler.removeCallbacks(mStatusChecker);
        super.onPause();
    }
}
