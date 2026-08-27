package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.NeonCyanBg
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary

@Composable
fun AiAnalysisCard(
    aiAnalysisText: String,
    modifier: Modifier = Modifier
) {
    CyberCard(
        modifier = modifier,
        borderColor = NeonCyan.copy(alpha = 0.35f),
        borderWidth = 1.2f
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = NeonCyan,
                    modifier = Modifier.size(16.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "COMMANDER DADANG WAHYUONO • AI ANALYSIS",
                    fontSize = 10.5.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = NeonCyan,
                    letterSpacing = 0.8.sp
                )
            }

            // Formatted AI text with [[levels]] parsed
            val annotatedText = parseAiAnalysisText(aiAnalysisText)
            Text(
                text = annotatedText,
                fontSize = 13.sp,
                lineHeight = 19.sp,
                color = TextPrimary,
                modifier = Modifier.padding(bottom = 12.dp)
            )

            // Permanent Static Financial Disclaimer as instructed
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(NeonCyanBg.copy(alpha = 0.5f))
                    .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(6.dp))
                    .padding(horizontal = 8.dp, vertical = 6.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.WarningAmber,
                        contentDescription = null,
                        tint = NeonAmber,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Bukan saran finansial — keputusan & risiko di tangan Anda.",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Medium,
                        color = TextSecondary
                    )
                }
            }
        }
    }
}

fun parseAiAnalysisText(rawText: String) = buildAnnotatedString {
    if (rawText.isBlank()) {
        append("Memuat analisa AI pasar...")
        return@buildAnnotatedString
    }

    val pattern = Regex("\\[\\[(.*?)\\]\\]")
    var lastIndex = 0

    pattern.findAll(rawText).forEach { matchResult ->
        val startIndex = matchResult.range.first
        val endIndex = matchResult.range.last + 1
        val extractedValue = matchResult.groupValues[1]

        // Append text preceding match
        if (startIndex > lastIndex) {
            append(rawText.substring(lastIndex, startIndex))
        }

        // Append styled match
        withStyle(
            style = SpanStyle(
                color = GoldAccent,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                background = NeonCyanBg
            )
        ) {
            append(" $extractedValue ")
        }

        lastIndex = endIndex
    }

    if (lastIndex < rawText.length) {
        append(rawText.substring(lastIndex))
    }
}
