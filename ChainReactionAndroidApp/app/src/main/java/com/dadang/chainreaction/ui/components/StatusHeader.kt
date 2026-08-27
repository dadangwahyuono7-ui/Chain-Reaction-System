package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.ConnectionState

@Composable
fun TopStatusHeader(
    connectionState: ConnectionState,
    latencyMs: Long,
    eaVersion: String,
    isKeepScreenOn: Boolean = true,
    onToggleKeepScreenOn: () -> Unit = {},
    onOpenHudMode: () -> Unit,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier
) {
    val (statusColor, statusText) = when (connectionState) {
        ConnectionState.CONNECTED -> Pair(NeonGreen, "LIVE")
        ConnectionState.RECONNECTING -> Pair(NeonAmber, "RETRY")
        ConnectionState.DISCONNECTED -> Pair(NeonRed, "OFFLINE")
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "CHAIN REACTION",
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 1.2.sp,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.width(6.dp))
                if (eaVersion.isNotBlank()) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(BgCardElevated)
                            .border(BorderStroke(0.5.dp, BorderSubtle), RoundedCornerShape(4.dp))
                            .padding(horizontal = 4.dp, vertical = 1.dp)
                    ) {
                        Text(
                            text = eaVersion,
                            fontSize = 8.sp,
                            fontFamily = FontFamily.Monospace,
                            color = TextMuted
                        )
                    }
                }
            }
            Text(
                text = "BY COMMANDER DADANG WAHYUONO",
                fontSize = 8.5.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 0.8.sp,
                color = GoldAccent
            )
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = 1.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(statusColor)
                )
                Spacer(modifier = Modifier.width(5.dp))
                Text(
                    text = statusText,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = statusColor
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "•",
                    fontSize = 10.sp,
                    color = TextMuted
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "${latencyMs}ms",
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    color = if (latencyMs < 200) TextSecondary else NeonAmber
                )
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            // Keep Screen On Toggle Button
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (isKeepScreenOn) GoldAccent.copy(alpha = 0.15f) else BgCardElevated)
                    .border(
                        BorderStroke(1.dp, if (isKeepScreenOn) GoldAccent else BorderSubtle),
                        RoundedCornerShape(8.dp)
                    )
                    .clickable { onToggleKeepScreenOn() }
                    .padding(horizontal = 6.dp, vertical = 6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Lightbulb,
                    contentDescription = "Keep Screen On",
                    tint = if (isKeepScreenOn) GoldAccent else TextMuted,
                    modifier = Modifier.size(16.dp)
                )
            }

            Spacer(modifier = Modifier.width(6.dp))

            // HUD Mode Toggle Button
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .background(BgCardElevated)
                    .border(BorderStroke(1.dp, NeonCyan.copy(alpha = 0.5f)), RoundedCornerShape(8.dp))
                    .clickable { onOpenHudMode() }
                    .padding(horizontal = 8.dp, vertical = 6.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Fullscreen,
                        contentDescription = "Commander HUD Mode",
                        tint = NeonCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = "HUD",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace,
                        color = NeonCyan
                    )
                }
            }

            Spacer(modifier = Modifier.width(4.dp))

            IconButton(
                onClick = onRefresh,
                modifier = Modifier.size(32.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Refresh,
                    contentDescription = "Refresh Data",
                    tint = TextSecondary,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}
