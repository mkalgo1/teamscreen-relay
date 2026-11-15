package com.teamscreen.support;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;

public class RemoteInputService extends AccessibilityService {
    private static final String TAG = "RemoteInputService";
    private static RemoteInputService sInstance;

    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        sInstance = this;
        Log.i(TAG, "Accessibility Service Connected: Remote input ready");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Passive listener
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "Accessibility Service Interrupted");
    }

    @Override
    public void onDestroy() {
        if (sInstance == this) {
            sInstance = null;
        }
        super.onDestroy();
        Log.i(TAG, "Accessibility Service Destroyed");
    }

    public static boolean isServiceActive() {
        return sInstance != null;
    }

    public static boolean dispatchTap(float xRatio, float yRatio) {
        if (sInstance == null) {
            Log.w(TAG, "Cannot dispatch tap: AccessibilityService not connected");
            return false;
        }

        try {
            DisplayMetrics metrics = sInstance.getResources().getDisplayMetrics();
            float x = Math.max(0, Math.min(metrics.widthPixels - 1, xRatio * metrics.widthPixels));
            float y = Math.max(0, Math.min(metrics.heightPixels - 1, yRatio * metrics.heightPixels));

            Path path = new Path();
            path.moveTo(x, y);

            GestureDescription.Builder builder = new GestureDescription.Builder();
            builder.addStroke(new GestureDescription.StrokeDescription(path, 0, 50));

            return sInstance.dispatchGesture(builder.build(), new GestureResultCallback() {
                @Override
                public void onCompleted(GestureDescription gestureDescription) {
                    super.onCompleted(gestureDescription);
                    Log.d(TAG, "Tap executed successfully at (" + x + ", " + y + ")");
                }

                @Override
                public void onCancelled(GestureDescription gestureDescription) {
                    super.onCancelled(gestureDescription);
                    Log.w(TAG, "Tap cancelled at (" + x + ", " + y + ")");
                }
            }, null);
        } catch (Exception e) {
            Log.e(TAG, "Error dispatching tap", e);
            return false;
        }
    }
}
