package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonAmberBg
import com.dadang.chainreaction.ui.theme.NeonAmberBorder
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonCyanBg
import com.dadang.chainreaction.ui.theme.NeonCyanBorder
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonGreenBg
import com.dadang.chainreaction.ui.theme.NeonGreenBorder
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.NeonRedBg
import com.dadang.chainreaction.ui.theme.NeonRedBorder
import com.dadang.chainreaction.ui.theme.TextMuted

@Composable
fun DirectionPill(
    direction: String,
    modifier: Modifier = Modifier,
    fontSize: TextUnit = 11.sp,
    forceUppercase: Boolean = true
) {
    val dirNorm = direction.trim().uppercase()

    val (bgColor, borderColor, textColor) = when {
        dirNorm.contains("BUY") || dirNorm.contains("BULLISH") || dirNorm.contains("UP") -> {
            Triple(NeonGreenBg, NeonGreenBorder, NeonGreen)
        }
        dirNorm.contains("SELL") || dirNorm.contains("BEARISH") || dirNorm.contains("DOWN") -> {
            Triple(NeonRedBg, NeonRedBorder, NeonRed)
        }
        dirNorm.contains("WAIT") || dirNorm.contains("HATI-HATI") || dirNorm.contains("OBSERVE") || dirNorm.contains("WARNING") -> {
            Triple(NeonAmberBg, NeonAmberBorder, NeonAmber)
        }
        dirNorm.contains("SIDEWAYS") || dirNorm.contains("IN") || dirNorm.contains("INSIDE") || dirNorm.contains("INFO") -> {
            Triple(NeonCyanBg, NeonCyanBorder, NeonCyan)
        }
        else -> {
            Triple(Color(0xFF1E293B), Color(0xFF334155), TextMuted)
        }
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(bgColor)
            .border(BorderStroke(1.dp, borderColor), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp)
    ) {
        Text(
            text = if (forceUppercase) dirNorm else direction,
            fontSize = fontSize,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            color = textColor
        )
    }
}
