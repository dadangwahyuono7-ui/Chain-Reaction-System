package com.dadang.chainreaction.service

import android.content.Context
import android.content.SharedPreferences

class NotificationPreferences(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    var isNotificationsEnabled: Boolean
        get() = prefs.getBoolean(KEY_ALL_NOTIFICATIONS, true)
        set(value) = prefs.edit().putBoolean(KEY_ALL_NOTIFICATIONS, value).apply()

    // Multi-Timeframe Breakout / Flip Toggles (D1, H4, H1, M30, M15, M5)
    var isD1FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_D1_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_D1_FLIP, value).apply()

    var isH4FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_H4_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_H4_FLIP, value).apply()

    var isH1FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_H1_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_H1_FLIP, value).apply()

    var isM30FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_M30_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_M30_FLIP, value).apply()

    var isM15FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_M15_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_M15_FLIP, value).apply()

    var isM5FlipEnabled: Boolean
        get() = prefs.getBoolean(KEY_M5_FLIP, true)
        set(value) = prefs.edit().putBoolean(KEY_M5_FLIP, value).apply()

    // Other core trading alerts
    var isActionChangeEnabled: Boolean
        get() = prefs.getBoolean(KEY_ACTION_CHANGE, true)
        set(value) = prefs.edit().putBoolean(KEY_ACTION_CHANGE, value).apply()

    var isChainUpgradeEnabled: Boolean
        get() = prefs.getBoolean(KEY_CHAIN_UPGRADE, true)
        set(value) = prefs.edit().putBoolean(KEY_CHAIN_UPGRADE, value).apply()

    var isWallSweepEnabled: Boolean
        get() = prefs.getBoolean(KEY_WALL_SWEEP, true)
        set(value) = prefs.edit().putBoolean(KEY_WALL_SWEEP, value).apply()

    var isHighImpactNewsEnabled: Boolean
        get() = prefs.getBoolean(KEY_NEWS_ALERT, true)
        set(value) = prefs.edit().putBoolean(KEY_NEWS_ALERT, value).apply()

    var isConfluenceAlertEnabled: Boolean
        get() = prefs.getBoolean(KEY_CONFLUENCE_ALERT, true)
        set(value) = prefs.edit().putBoolean(KEY_CONFLUENCE_ALERT, value).apply()

    var isZoneTouchEnabled: Boolean
        get() = prefs.getBoolean(KEY_ZONE_TOUCH, true)
        set(value) = prefs.edit().putBoolean(KEY_ZONE_TOUCH, value).apply()

    var isSoundVibrateEnabled: Boolean
        get() = prefs.getBoolean(KEY_SOUND_VIBRATE, true)
        set(value) = prefs.edit().putBoolean(KEY_SOUND_VIBRATE, value).apply()

    fun isTfFlipEnabled(tf: String): Boolean {
        return when (tf.uppercase()) {
            "D1" -> isD1FlipEnabled
            "H4" -> isH4FlipEnabled
            "H1" -> isH1FlipEnabled
            "M30" -> isM30FlipEnabled
            "M15" -> isM15FlipEnabled
            "M5" -> isM5FlipEnabled
            else -> isM5FlipEnabled
        }
    }

    companion object {
        private const val PREF_NAME = "chain_reaction_notif_prefs"
        private const val KEY_ALL_NOTIFICATIONS = "all_notifications"
        private const val KEY_D1_FLIP = "d1_flip"
        private const val KEY_H4_FLIP = "h4_flip"
        private const val KEY_H1_FLIP = "h1_flip"
        private const val KEY_M30_FLIP = "m30_flip"
        private const val KEY_M15_FLIP = "m15_flip"
        private const val KEY_M5_FLIP = "m5_flip"
        private const val KEY_ACTION_CHANGE = "action_change"
        private const val KEY_CHAIN_UPGRADE = "chain_upgrade"
        private const val KEY_WALL_SWEEP = "wall_sweep"
        private const val KEY_NEWS_ALERT = "news_alert"
        private const val KEY_CONFLUENCE_ALERT = "confluence_alert"
        private const val KEY_ZONE_TOUCH = "zone_touch"
        private const val KEY_SOUND_VIBRATE = "sound_vibrate"

        @Volatile
        private var instance: NotificationPreferences? = null

        fun getInstance(context: Context): NotificationPreferences {
            return instance ?: synchronized(this) {
                instance ?: NotificationPreferences(context.applicationContext).also { instance = it }
            }
        }
    }
}
