package com.dadang.chainreaction.data.model

import com.google.gson.annotations.SerializedName

data class NewsFeed(
    @SerializedName("updated_ts") val updatedTs: Double = 0.0,
    val source: String = "",
    val items: List<NewsItem> = emptyList(),
    val conclusion: NewsConclusion = NewsConclusion(),
    @SerializedName("ai_analysis") val aiAnalysis: String = ""
)

data class NewsItem(
    val title: String? = null,
    @SerializedName("title_id") val titleId: String? = null,
    val summary: String? = null,
    @SerializedName("summary_id") val summaryId: String? = null,
    val category: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    val link: String? = null,
    val tone: String = "NEUTRAL",
    val confluences: List<NewsConfluence> = emptyList()
) {
    val displayTitle: String
        get() = if (!titleId.isNullOrBlank()) titleId else title ?: "Tanpa Judul"

    val displaySummary: String
        get() = if (!summaryId.isNullOrBlank()) summaryId else summary ?: ""
}

data class NewsConfluence(
    val level: Double = 0.0,
    @SerializedName("matched_price") val matchedPrice: Double = 0.0,
    @SerializedName("matched_label") val matchedLabel: String = "",
    val distance: Double = 0.0
)

data class NewsConclusion(
    @SerializedName("bullish_count") val bullishCount: Int = 0,
    @SerializedName("bearish_count") val bearishCount: Int = 0,
    @SerializedName("neutral_count") val neutralCount: Int = 0,
    val total: Int = 0,
    val verdict: String = "NEUTRAL"
)
