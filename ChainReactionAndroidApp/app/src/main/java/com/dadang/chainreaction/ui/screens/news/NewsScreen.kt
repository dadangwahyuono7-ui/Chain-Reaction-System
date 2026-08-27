package com.dadang.chainreaction.ui.screens.news

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Newspaper
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.NewsConclusion
import com.dadang.chainreaction.data.model.NewsFeed
import com.dadang.chainreaction.data.model.NewsItem
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.ui.components.AiAnalysisCard
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
import com.dadang.chainreaction.ui.theme.NeonGreen
import com.dadang.chainreaction.ui.theme.NeonRed
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary
import com.dadang.chainreaction.ui.theme.TextSecondary
import com.dadang.chainreaction.util.Formatters

@Composable
fun NewsScreen(
    viewModel: NewsViewModel,
    onNavigateToDetail: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val newsFeed by viewModel.newsFeed.collectAsState()
    val calendarEvents by viewModel.calendarEvents.collectAsState()
    val sultanStatus by viewModel.sultanStatus.collectAsState()
    val selectedFilter by viewModel.selectedImpactFilter.collectAsState()

    if (newsFeed == null && calendarEvents.isEmpty()) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .background(BgCyberDark),
            contentAlignment = Alignment.Center
        ) {
            CircularProgressIndicator(color = NeonCyan, modifier = Modifier.size(36.dp))
        }
        return
    }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(BgCyberDark)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // 1. AI Market Analysis Card with Highlighted Levels & Permanent Disclaimer
        newsFeed?.let { feed ->
            item {
                AiAnalysisCard(aiAnalysisText = feed.aiAnalysis)
            }

            // 2. News Tone Summary Matrix
            item {
                NewsConclusionCard(conclusion = feed.conclusion)
            }

            // 3. News Articles List Header
            item {
                SectionHeader(
                    title = "MARKET NEWS FEED",
                    icon = Icons.Default.Newspaper,
                    badgeText = "${feed.items.size} ARTICLES",
                    badgeColor = NeonCyan
                )
            }

            // News Items
            itemsIndexed(feed.items) { index, item ->
                NewsArticleCard(
                    item = item,
                    onClick = { onNavigateToDetail(index) }
                )
            }
        }

        // 4. Economic Calendar (Forex Factory)
        item {
            Spacer(modifier = Modifier.height(10.dp))
            SectionHeader(
                title = "ECONOMIC CALENDAR (USD & GOLD)",
                icon = Icons.Default.CalendarMonth,
                badgeText = "UPCOMING",
                badgeColor = GoldAccent
            )
        }

        // Calendar Filter Tabs
        item {
            CalendarFilterRow(
                selectedFilter = selectedFilter,
                onSelectFilter = { viewModel.setImpactFilter(it) }
            )
        }

        val filteredEvents = calendarEvents.filter { event ->
            if (selectedFilter == "ALL") true else event.impact.equals(selectedFilter, ignoreCase = true)
        }

        itemsIndexed(filteredEvents) { _, event ->
            CalendarEventCard(event = event)
        }

        item {
            Spacer(modifier = Modifier.height(80.dp))
        }
    }
}

@Composable
private fun NewsConclusionCard(conclusion: NewsConclusion) {
    CyberCard {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "NEWS SENTIMENT OVERVIEW",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = TextMuted
                )
                DirectionPill(direction = "VERDICT: ${conclusion.verdict}", fontSize = 9.sp)
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                MetricBox(
                    label = "Bullish",
                    value = "${conclusion.bullishCount}",
                    valueColor = NeonGreen,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Bearish",
                    value = "${conclusion.bearishCount}",
                    valueColor = NeonRed,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Neutral",
                    value = "${conclusion.neutralCount}",
                    valueColor = TextSecondary,
                    modifier = Modifier.weight(1f)
                )
                MetricBox(
                    label = "Total",
                    value = "${conclusion.total}",
                    valueColor = NeonCyan,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun NewsArticleCard(
    item: NewsItem,
    onClick: () -> Unit
) {
    CyberCard(
        modifier = Modifier.clickable { onClick() }
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                DirectionPill(direction = item.tone, fontSize = 9.sp)
                Icon(
                    imageVector = Icons.Default.ChevronRight,
                    contentDescription = "Detail",
                    tint = TextSecondary,
                    modifier = Modifier.size(18.dp)
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = item.displayTitle,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
                lineHeight = 18.sp
            )

            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = item.displaySummary,
                fontSize = 11.sp,
                color = TextSecondary,
                maxLines = 2,
                lineHeight = 15.sp
            )

            // Confluences Chips
            if (item.confluences.isNotEmpty()) {
                Spacer(modifier = Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    item.confluences.forEach { conf ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(GoldAccent.copy(alpha = 0.12f))
                                .border(BorderStroke(0.6.dp, GoldAccent.copy(alpha = 0.4f)), RoundedCornerShape(4.dp))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = "🎯 ${conf.matchedLabel} @ ${Formatters.formatPrice(conf.matchedPrice)}",
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace,
                                color = GoldAccent
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CalendarFilterRow(
    selectedFilter: String,
    onSelectFilter: (String) -> Unit
) {
    val filters = listOf("ALL", "HIGH", "MEDIUM", "LOW")

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        filters.forEach { filter ->
            val isSelected = selectedFilter.equals(filter, ignoreCase = true)
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (isSelected) NeonCyan.copy(alpha = 0.2f) else BgCardElevated)
                    .border(
                        BorderStroke(0.8.dp, if (isSelected) NeonCyan else BorderSubtle),
                        RoundedCornerShape(6.dp)
                    )
                    .clickable { onSelectFilter(filter) }
                    .padding(horizontal = 10.dp, vertical = 6.dp)
            ) {
                Text(
                    text = filter,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = if (isSelected) NeonCyan else TextSecondary
                )
            }
        }
    }
}

@Composable
private fun CalendarEventCard(event: CalendarEvent) {
    val impactColor = when (event.impact.lowercase()) {
        "high" -> NeonRed
        "medium" -> NeonAmber
        else -> TextSecondary
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(BgCardElevated)
            .border(BorderStroke(0.8.dp, BorderSubtle), RoundedCornerShape(8.dp))
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(impactColor)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = event.name,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary
                    )
                    Row(modifier = Modifier.padding(top = 2.dp)) {
                        Text(
                            text = "Jam: ${event.time} • ",
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = TextMuted
                        )
                        if (event.forecast.isNotBlank()) {
                            Text(
                                text = "FC: ${event.forecast} | Prev: ${event.previous}",
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                color = TextSecondary
                            )
                        }
                    }
                }
            }

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(4.dp))
                    .background(impactColor.copy(alpha = 0.15f))
                    .border(BorderStroke(0.6.dp, impactColor.copy(alpha = 0.5f)), RoundedCornerShape(4.dp))
                    .padding(horizontal = 6.dp, vertical = 3.dp)
            ) {
                Text(
                    text = Formatters.formatMinsUntil(event.minsUntil),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    color = impactColor
                )
            }
        }
    }
}
