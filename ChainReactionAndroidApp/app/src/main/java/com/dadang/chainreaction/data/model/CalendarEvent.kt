package com.dadang.chainreaction.data.model

import com.google.gson.annotations.SerializedName

data class CalendarEvent(
    val name: String = "",
    val time: String = "",
    val released: Boolean = false,
    @SerializedName("mins_until") val minsUntil: Long = 0L,
    val country: String = "USD",
    val forecast: String = "",
    val previous: String = "",
    val impact: String = "low" // low, medium, high
)
