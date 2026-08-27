package com.dadang.chainreaction.ui.screens.news

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.OpenInBrowser
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.NewsItem
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.ui.components.CyberCard
import com.dadang.chainreaction.ui.components.DirectionPill
import com.dadang.chainreaction.ui.components.MetricBox
import com.dadang.chainreaction.ui.components.SectionHeader
import com.dadang.chainreaction.ui.theme.BgCardElevated
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.GoldAccent
import com.dadang.chainreaction.ui.theme.NeonAmber
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

@Composable
fun NewsDetailScreen(
    item: NewsItem?,
    sultanStatus: SultanStatus?,
    onNavigateBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current

    if (item == null) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(BgCyberDark),
            contentAlignment = Alignment.Center
        ) {
            Text("Artikel berita tidak ditemukan.", color = TextSecondary)
        }
        return
    }

    val scrollState = rememberScrollState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(BgCyberDark)
            .verticalScroll(scrollState)
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Top Back Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onNavigateBack) {
                Icon(
                    imageVector = Icons.Default.ArrowBack,
                    contentDescription = "Back",
                    tint = TextPrimary
                )
            }
            Spacer(modifier = Modifier.width(4.dp))
            Text(
                text = "DETAIL ARTIKEL BERITA",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = NeonCyan,
                letterSpacing = 1.sp
            )
            Spacer(modifier = Modifier.weight(1f))
            DirectionPill(direction = item.tone)
        }

        // Title & Metadata
        CyberCard {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = item.displayTitle,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary,
                    lineHeight = 22.sp
                )

                if (!item.category.isNullOrBlank() || !item.createdAt.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "Kategori: ${item.category ?: "Umum"} ${if (!item.createdAt.isNullOrBlank()) "• " + item.createdAt else ""}",
                        fontSize = 10.sp,
                        color = TextMuted
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = item.displaySummary,
                    fontSize = 13.sp,
                    color = TextSecondary,
                    lineHeight = 20.sp
                )
            }
        }

        // Confluences Section
        if (item.confluences.isNotEmpty()) {
            CyberCard {
                Column(modifier = Modifier.fillMaxWidth()) {
                    SectionHeader(
                        title = "CONFLUENCE KEY LEVELS",
                        badgeText = "${item.confluences.size} MATCHED",
                        badgeColor = GoldAccent
                    )
                    item.confluences.forEach { conf ->
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 3.dp)
                                .clip(RoundedCornerShape(6.dp))
                                .background(BgCardElevated)
                                .border(BorderStroke(0.6.dp, BorderSubtle), RoundedCornerShape(6.dp))
                                .padding(8.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Target Level: $${Formatters.formatPrice(conf.level)}",
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = TextPrimary
                                )
                                Text(
                                    text = "${conf.matchedLabel} @ $${Formatters.formatPrice(conf.matchedPrice)} (${conf.distance}p)",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace,
                                    color = GoldAccent
                                )
                            }
                        }
                    }
                }
            }
        }

        // Related Levels from Live Status
        if (sultanStatus != null) {
            CyberCard {
                Column(modifier = Modifier.fillMaxWidth()) {
                    SectionHeader(
                        title = "RELATED VALUE AREA LEVELS",
                        badgeText = "LIVE STATUS",
                        badgeColor = NeonCyan
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        MetricBox(
                            label = "VAL",
                            value = Formatters.formatPrice(sultanStatus.location.valPrice),
                            valueColor = NeonCyan,
                            modifier = Modifier.weight(1f)
                        )
                        MetricBox(
                            label = "POC",
                            value = Formatters.formatPrice(sultanStatus.location.poc),
                            valueColor = GoldAccent,
                            modifier = Modifier.weight(1f)
                        )
                        MetricBox(
                            label = "VAH",
                            value = Formatters.formatPrice(sultanStatus.location.vahPrice),
                            valueColor = NeonCyan,
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
            }
        }

        // Implikasi ke Chain Reaction (Honest placeholder per prompt)
        CyberCard {
            Column(modifier = Modifier.fillMaxWidth()) {
                SectionHeader(title = "IMPLIKASI KE CHAIN REACTION")
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(6.dp))
                        .background(BgCardElevated)
                        .padding(10.dp)
                ) {
                    Text(
                        text = "ℹ️ Modul AI Implikasi per-artikel sedang disiapkan di backend dan akan aktif otomatis saat update backend berikutnya.",
                        fontSize = 11.sp,
                        color = TextMuted,
                        lineHeight = 16.sp
                    )
                }
            }
        }

        // Open Source URL Button
        if (!item.link.isNullOrBlank()) {
            Button(
                onClick = {
                    try {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(item.link))
                        context.startActivity(intent)
                    } catch (_: Exception) {}
                },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = BgCardElevated,
                    contentColor = NeonCyan
                ),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.5f))
            ) {
                Icon(
                    imageVector = Icons.Default.OpenInBrowser,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Buka Artikel Sumber di Browser",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        Spacer(modifier = Modifier.height(40.dp))
    }
}
