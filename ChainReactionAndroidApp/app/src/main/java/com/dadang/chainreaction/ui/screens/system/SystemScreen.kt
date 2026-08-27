package com.dadang.chainreaction.ui.screens.system

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.BatteryChargingFull
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.NetworkCheck
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.SystemHealth
import com.dadang.chainreaction.service.BatteryOptimizationHelper
import com.dadang.chainreaction.service.KeepAliveService
import com.dadang.chainreaction.service.NotificationHelper
import com.dadang.chainreaction.service.NotificationPreferences
import com.dadang.chainreaction.ui.components.CyberCard
import com.dadang.chainreaction.ui.components.MetricBox
import com.dadang.chainreaction.ui.components.SectionHeader
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonGreenBg
import com.dadang.chainreaction.ui.theme.NeonGreenBorder
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

@Composable
fun SystemScreen(
    status: SultanStatus?,
    health: SystemHealth?,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val notifPrefs = remember { NotificationPreferences.getInstance(context) }
    val notifHelper = remember { NotificationHelper.getInstance(context) }

    var isKeepAliveEnabled by remember { mutableStateOf(true) }
    var isNotifAllEnabled by remember { mutableStateOf(notifPrefs.isNotificationsEnabled) }

    // Multi-TF Flip states
    var isD1FlipEnabled by remember { mutableStateOf(notifPrefs.isD1FlipEnabled) }
    var isH4FlipEnabled by remember { mutableStateOf(notifPrefs.isH4FlipEnabled) }
    var isH1FlipEnabled by remember { mutableStateOf(notifPrefs.isH1FlipEnabled) }
    var isM30FlipEnabled by remember { mutableStateOf(notifPrefs.isM30FlipEnabled) }
    var isM15FlipEnabled by remember { mutableStateOf(notifPrefs.isM15FlipEnabled) }
    var isM5FlipEnabled by remember { mutableStateOf(notifPrefs.isM5FlipEnabled) }

    var isActionChangeEnabled by remember { mutableStateOf(notifPrefs.isActionChangeEnabled) }
    var isChainUpgradeEnabled by remember { mutableStateOf(notifPrefs.isChainUpgradeEnabled) }
    var isWallSweepEnabled by remember { mutableStateOf(notifPrefs.isWallSweepEnabled) }
    var isNewsAlertEnabled by remember { mutableStateOf(notifPrefs.isHighImpactNewsEnabled) }
    var isSoundVibrateEnabled by remember { mutableStateOf(notifPrefs.isSoundVibrateEnabled) }

    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BgCyberDark)
            .verticalScroll(scrollState)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // 0. Terminal Identity Badge
        TerminalIdentityCard()

        // 1. Trading Signal Notifications Settings Card (Multi-TF Breakout & Alerts)
        NotificationSettingsCard(
            isAllEnabled = isNotifAllEnabled,
            onToggleAll = {
                isNotifAllEnabled = it
                notifPrefs.isNotificationsEnabled = it
            },
            isD1 = isD1FlipEnabled,
            onToggleD1 = { isD1FlipEnabled = it; notifPrefs.isD1FlipEnabled = it },
            isH4 = isH4FlipEnabled,
            onToggleH4 = { isH4FlipEnabled = it; notifPrefs.isH4FlipEnabled = it },
            isH1 = isH1FlipEnabled,
            onToggleH1 = { isH1FlipEnabled = it; notifPrefs.isH1FlipEnabled = it },
            isM30 = isM30FlipEnabled,
            onToggleM30 = { isM30FlipEnabled = it; notifPrefs.isM30FlipEnabled = it },
            isM15 = isM15FlipEnabled,
            onToggleM15 = { isM15FlipEnabled = it; notifPrefs.isM15FlipEnabled = it },
            isM5 = isM5FlipEnabled,
            onToggleM5 = { isM5FlipEnabled = it; notifPrefs.isM5FlipEnabled = it },
            isAction = isActionChangeEnabled,
            onToggleAction = {
                isActionChangeEnabled = it
                notifPrefs.isActionChangeEnabled = it
            },
            isChain = isChainUpgradeEnabled,
            onToggleChain = {
                isChainUpgradeEnabled = it
                notifPrefs.isChainUpgradeEnabled = it
            },
            isWallSweep = isWallSweepEnabled,
            onToggleWallSweep = {
                isWallSweepEnabled = it
                notifPrefs.isWallSweepEnabled = it
            },
            isNews = isNewsAlertEnabled,
            onToggleNews = {
                isNewsAlertEnabled = it
                notifPrefs.isHighImpactNewsEnabled = it
            },
            isSoundVibrate = isSoundVibrateEnabled,
            onToggleSoundVibrate = {
                isSoundVibrateEnabled = it
                notifPrefs.isSoundVibrateEnabled = it
            },
            onTestNotification = {
                notifHelper.sendTestNotification()
            }
        )

        // 2. Backend Server PC Health (GET /api/system_health)
        ServerHealthCard(health = health)

        // 3. Engine & Network Connection Status
        EngineStatusCard(status = status)

        // 4. Trading Account Equity Overview
        AccountOverviewCard(status = status)

        // 5. Background Keep-Alive & Battery Optimization Controls
        BackgroundKeepAliveCard(
            isKeepAliveEnabled = isKeepAliveEnabled,
            onToggleKeepAlive = { enabled ->
                isKeepAliveEnabled = enabled
                if (enabled) {
                    KeepAliveService.start(context)
                } else {
                    KeepAliveService.stop(context)
                }
            },
            onRequestBatteryOptimization = {
                BatteryOptimizationHelper.requestIgnoreBatteryOptimization(context)
            }
        )

        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun TerminalIdentityCard() {
    CyberCard(
        borderColor = GoldAccent.copy(alpha = 0.4f),
        borderWidth = 1.2f
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "COMMANDER DADANG WAHYUONO",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Black,
                    fontFamily = FontFamily.Monospace,
                    color = GoldAccent,
                    letterSpacing = 1.sp
                )
                Text(
                    text = "Automated Order-Flow & Gold Reaction Engine",
                    fontSize = 10.sp,
                    color = TextSecondary
                )
            }
            Icon(
                imageVector = Icons.Default.Shield,
                contentDescription = null,
                tint = GoldAccent,
                modifier = Modifier.size(22.dp)
            )
        }
    }
}

@Composable
private fun NotificationSettingsCard(
    isAllEnabled: Boolean,
    onToggleAll: (Boolean) -> Unit,
    isD1: Boolean,
    onToggleD1: (Boolean) -> Unit,
    isH4: Boolean,
    onToggleH4: (Boolean) -> Unit,
    isH1: Boolean,
    onToggleH1: (Boolean) -> Unit,
    isM30: Boolean,
    onToggleM30: (Boolean) -> Unit,
    isM15: Boolean,
    onToggleM15: (Boolean) -> Unit,
    isM5: Boolean,
    onToggleM5: (Boolean) -> Unit,
    isAction: Boolean,
    onToggleAction: (Boolean) -> Unit,
    isChain: Boolean,
    onToggleChain: (Boolean) -> Unit,
    isWallSweep: Boolean,
    onToggleWallSweep: (Boolean) -> Unit,
    isNews: Boolean,
    onToggleNews: (Boolean) -> Unit,
    isSoundVibrate: Boolean,
    onToggleSoundVibrate: (Boolean) -> Unit,
    onTestNotification: () -> Unit
) {
    CyberCard(borderColor = NeonCyan.copy(alpha = 0.35f)) {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "TRADING SIGNAL NOTIFICATIONS",
                icon = Icons.Default.NotificationsActive,
                badgeText = if (isAllEnabled) "ACTIVE" else "MUTED",
                badgeColor = if (isAllEnabled) NeonGreen else NeonAmber
            )

            // Master Switch
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Master Notifikasi Trading",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                    Text(
                        text = "Mengirimkan heads-up alert saat ada sinyal & breakout",
                        fontSize = 11.sp,
                        color = TextSecondary
                    )
                }
                Switch(
                    checked = isAllEnabled,
                    onCheckedChange = onToggleAll,
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = NeonCyan,
                        checkedTrackColor = NeonCyan.copy(alpha = 0.3f)
                    )
                )
            }

            if (isAllEnabled) {
                Spacer(modifier = Modifier.height(10.dp))

                // Multi-Timeframe Breakout / Flip Chips Header
                Text(
                    text = "BREAKOUT & REGIME FLIP NOTIFIKASI PER-TIMEFRAME:",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan
                )

                Spacer(modifier = Modifier.height(6.dp))

                // Row of TF Toggle Chips
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    TfToggleChip(tf = "D1", enabled = isD1, onToggle = onToggleD1, modifier = Modifier.weight(1f))
                    TfToggleChip(tf = "H4", enabled = isH4, onToggle = onToggleH4, modifier = Modifier.weight(1f))
                    TfToggleChip(tf = "H1", enabled = isH1, onToggle = onToggleH1, modifier = Modifier.weight(1f))
                    TfToggleChip(tf = "M30", enabled = isM30, onToggle = onToggleM30, modifier = Modifier.weight(1f))
                    TfToggleChip(tf = "M15", enabled = isM15, onToggle = onToggleM15, modifier = Modifier.weight(1f))
                    TfToggleChip(tf = "M5", enabled = isM5, onToggle = onToggleM5, modifier = Modifier.weight(1f))
                }

                Spacer(modifier = Modifier.height(8.dp))

                NotifToggleRow(
                    label = "Primary Action Shift (BUY / SELL)",
                    checked = isAction,
                    onCheckedChange = onToggleAction
                )
                NotifToggleRow(
                    label = "Chain Reaction Layer Progression (Layer 3+)",
                    checked = isChain,
                    onCheckedChange = onToggleChain
                )
                NotifToggleRow(
                    label = "Bookmap Wall Sweep Lot Besar",
                    checked = isWallSweep,
                    onCheckedChange = onToggleWallSweep
                )
                NotifToggleRow(
                    label = "High-Impact News (Forex Factory 10m)",
                    checked = isNews,
                    onCheckedChange = onToggleNews
                )
                NotifToggleRow(
                    label = "Suara & Getar (Sound & Vibrate)",
                    checked = isSoundVibrate,
                    onCheckedChange = onToggleSoundVibrate
                )

                Spacer(modifier = Modifier.height(10.dp))

                // Test Notification Button
                Button(
                    onClick = onTestNotification,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = BgCardElevated,
                        contentColor = NeonCyan
                    ),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.5f))
                ) {
                    Icon(
                        imageVector = Icons.Default.VolumeUp,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Test Bunyikan Notifikasi Sinyal",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
    }
}

@Composable
private fun TfToggleChip(
    tf: String,
    enabled: Boolean,
    onToggle: (Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(if (enabled) NeonGreenBg else BgCardElevated)
            .border(
                BorderStroke(0.8.dp, if (enabled) NeonGreenBorder else BorderSubtle),
                RoundedCornerShape(6.dp)
            )
            .clickable { onToggle(!enabled) }
            .padding(vertical = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = tf,
            fontSize = 10.5.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            color = if (enabled) NeonGreen else TextMuted
        )
    }
}

@Composable
private fun NotifToggleRow(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            fontSize = 11.5.sp,
            color = if (checked) TextPrimary else TextMuted,
            modifier = Modifier.weight(1f)
        )
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.padding(start = 8.dp),
            colors = SwitchDefaults.colors(
                checkedThumbColor = NeonGreen,
                checkedTrackColor = NeonGreen.copy(alpha = 0.3f)
            )
        )
    }
}

@Composable
private fun ServerHealthCard(health: SystemHealth?) {
    val cpu = health?.cpuPct ?: 0.0
    val memory = health?.memoryPct ?: 0.0
    val disk = health?.diskPct ?: 0.0

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "BACKEND SERVER HEALTH",
                icon = Icons.Default.Memory,
                badgeText = "MINI-PC ENGINE",
                badgeColor = NeonCyan
            )

            HealthGaugeRow(label = "CPU USAGE", pct = cpu)
            Spacer(modifier = Modifier.height(8.dp))
            HealthGaugeRow(label = "RAM / MEMORY", pct = memory)
            Spacer(modifier = Modifier.height(8.dp))
            HealthGaugeRow(label = "DISK STORAGE", pct = disk)
        }
    }
}

@Composable
private fun HealthGaugeRow(label: String, pct: Double) {
    val barColor = when {
        pct >= 85 -> NeonRed
        pct >= 65 -> NeonAmber
        else -> NeonGreen
    }

    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = TextSecondary
            )
            Text(
                text = Formatters.formatPercent(pct),
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                color = barColor
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp))
                .background(BgCardElevated)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth((pct / 100.0).toFloat().coerceIn(0.02f, 1f))
                    .height(6.dp)
                    .background(barColor)
            )
        }
    }
}

@Composable
private fun EngineStatusCard(status: SultanStatus?) {
    val isOnline = status?.dataStatus?.bookmapOnline == true
    val latency = status?.dataStatus?.bridgeLatencyMs ?: 0L

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "ENGINE & DATA BRIDGE STATUS",
                icon = Icons.Default.NetworkCheck,
                badgeText = if (isOnline) "BOOKMAP LIVE" else "OFFLINE",
                badgeColor = if (isOnline) NeonGreen else NeonRed
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Bridge Latency",
                    value = "${latency} ms",
                    subValue = if (latency < 200) "Optimal" else "Tinggi",
                    valueColor = if (latency < 200) NeonGreen else NeonAmber,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "EA Version",
                    value = status?.eaVersion ?: "-",
                    valueColor = TextPrimary,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "App Version",
                    value = "v1.4.0",
                    subValue = "Multi-TF Flip",
                    valueColor = GoldAccent,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun AccountOverviewCard(status: SultanStatus?) {
    val bal = status?.balance ?: 0.0
    val eq = status?.equity ?: 0.0
    val pnl = eq - bal

    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "TRADING CAPITAL METRICS",
                icon = Icons.Default.AccountBalanceWallet,
                badgeText = "XAUUSD LIVE",
                badgeColor = GoldAccent
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Balance",
                    value = Formatters.formatCurrency(bal),
                    valueColor = TextPrimary,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Equity",
                    value = Formatters.formatCurrency(eq),
                    valueColor = if (eq >= bal) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Floating P&L",
                    value = (if (pnl >= 0) "+" else "") + Formatters.formatCurrency(pnl),
                    valueColor = if (pnl >= 0) NeonGreen else NeonRed,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun BackgroundKeepAliveCard(
    isKeepAliveEnabled: Boolean,
    onToggleKeepAlive: (Boolean) -> Unit,
    onRequestBatteryOptimization: () -> Unit
) {
    CyberCard(borderColor = NeonCyan.copy(alpha = 0.3f)) {
        Column(modifier = Modifier.fillMaxWidth()) {
            SectionHeader(
                title = "24/7 BACKGROUND KEEP-ALIVE",
                icon = Icons.Default.BatteryChargingFull,
                badgeText = "PERSISTENT",
                badgeColor = NeonCyan
            )

            // Switch Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Foreground Service",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                    Text(
                        text = "Menjaga koneksi polling live saat layar mati atau app di background",
                        fontSize = 11.sp,
                        color = TextSecondary,
                        lineHeight = 15.sp
                    )
                }
                Switch(
                    checked = isKeepAliveEnabled,
                    onCheckedChange = onToggleKeepAlive,
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = NeonCyan,
                        checkedTrackColor = NeonCyan.copy(alpha = 0.3f)
                    )
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Battery Optimization Button
            Button(
                onClick = onRequestBatteryOptimization,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = BgCardElevated,
                    contentColor = NeonAmber
                ),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, NeonAmber.copy(alpha = 0.5f))
            ) {
                Icon(
                    imageVector = Icons.Default.BatteryChargingFull,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "Buka Izin Abaikan Optimasi Baterai",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }
        }
    }
}
