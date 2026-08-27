package com.dadang.chainreaction

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.dadang.chainreaction.data.repository.TradingRepository
import com.dadang.chainreaction.service.KeepAliveService
import com.dadang.chainreaction.ui.navigation.AppNavigation
import com.dadang.chainreaction.ui.theme.ChainReactionTheme

class MainActivity : ComponentActivity() {

    private val repository = TradingRepository.getInstance()
    private var isKeepScreenOn by mutableStateOf(true)

    private val requestNotificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ ->
        KeepAliveService.start(this)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Enable Screen Always-On by default for live trading terminal
        applyKeepScreenOn(isKeepScreenOn)

        // Start Background Polling Engine
        repository.startPolling(lifecycleScope)

        // Request notification permission for Foreground Service on Android 13+
        checkAndRequestPermissions()

        setContent {
            ChainReactionTheme {
                AppNavigation(
                    isKeepScreenOn = isKeepScreenOn,
                    onToggleKeepScreenOn = {
                        isKeepScreenOn = !isKeepScreenOn
                        applyKeepScreenOn(isKeepScreenOn)
                    }
                )
            }
        }
    }

    private fun applyKeepScreenOn(enabled: Boolean) {
        if (enabled) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun checkAndRequestPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this,
                    Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                KeepAliveService.start(this)
            }
        } else {
            KeepAliveService.start(this)
        }
    }

    override fun onResume() {
        super.onResume()
        repository.startPolling(lifecycleScope)
    }
}
