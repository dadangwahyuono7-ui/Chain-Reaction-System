package com.dadang.chainreaction.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.ui.theme.BgCard
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary

@Composable
fun CyberCard(
    modifier: Modifier = Modifier,
    backgroundColor: Color = BgCard,
    borderColor: Color = BorderSubtle,
    borderWidth: Float = 1f,
    shapeRadius: Float = 12f,
    content: @Composable BoxScope.() -> Unit
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(shapeRadius.dp))
            .border(
                BorderStroke(borderWidth.dp, borderColor),
                RoundedCornerShape(shapeRadius.dp)
            ),
        color = backgroundColor,
        shape = RoundedCornerShape(shapeRadius.dp)
    ) {
        Box(
            modifier = Modifier.padding(14.dp),
            content = content
        )
    }
}

@Composable
fun SectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    iconTint: Color = NeonCyan,
    badgeText: String? = null,
    badgeColor: Color = NeonCyan,
    actionContent: (@Composable () -> Unit)? = null
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (icon != null) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
        }
        Text(
            text = title.uppercase(),
            style = androidx.compose.material3.MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
            color = TextSecondary,
            letterSpacing = 1.sp
        )
        if (badgeText != null) {
            Spacer(modifier = Modifier.width(8.dp))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(badgeColor.copy(alpha = 0.15f))
                    .border(BorderStroke(0.8.dp, badgeColor.copy(alpha = 0.5f)), RoundedCornerShape(4.dp))
                    .padding(horizontal = 6.dp, vertical = 2.dp)
            ) {
                Text(
                    text = badgeText,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = badgeColor
                )
            }
        }
        Spacer(modifier = Modifier.weight(1f))
        actionContent?.invoke()
    }
}

@Composable
fun MetricBox(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    subValue: String? = null,
    valueColor: Color = TextPrimary,
    accentColor: Color? = null
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(BgCardElevated)
            .border(
                BorderStroke(
                    0.8.dp,
                    accentColor?.copy(alpha = 0.4f) ?: BorderSubtle
                ),
                RoundedCornerShape(8.dp)
            )
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Column {
            Text(
                text = label.uppercase(),
                style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
                color = TextMuted,
                letterSpacing = 0.5.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = value,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = valueColor
            )
            if (!subValue.isNullOrBlank()) {
                Text(
                    text = subValue,
                    fontSize = 10.sp,
                    color = TextSecondary
                )
            }
        }
    }
}

@Composable
fun PulseDot(
    color: Color,
    modifier: Modifier = Modifier,
    size: Int = 8
) {
    Box(
        modifier = modifier
            .size(size.dp)
            .clip(CircleShape)
            .background(color)
    )
}
