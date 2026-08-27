package com.dadang.chainreaction.util

import java.text.DecimalFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object Formatters {

    private val priceFormatter = DecimalFormat("#,##0.00")
    private val integerFormatter = DecimalFormat("#,##0")
    private val oneDecimalFormatter = DecimalFormat("#,##0.0")
    private val timeFormatter = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    private val shortTimeFormatter = SimpleDateFormat("HH:mm", Locale.getDefault())

    fun formatPrice(price: Double): String {
        return priceFormatter.format(price)
    }

    fun formatCurrency(amount: Double): String {
        return "$" + priceFormatter.format(amount)
    }

    fun formatLot(lot: Double): String {
        return oneDecimalFormatter.format(lot)
    }

    fun formatPercent(pct: Double): String {
        return oneDecimalFormatter.format(pct) + "%"
    }

    fun formatCountdownSeconds(seconds: Long): String {
        if (seconds <= 0) return "00:00"
        val m = seconds / 60
        val s = seconds % 60
        return String.format(Locale.getDefault(), "%02d:%02d", m, s)
    }

    fun formatMinsUntil(mins: Long): String {
        if (mins <= 0) return "NOW"
        if (mins < 60) return "${mins}m"
        val h = mins / 60
        val m = mins % 60
        return if (m > 0) "${h}h ${m}m" else "${h}h"
    }

    fun formatTime(timestampSeconds: Long): String {
        if (timestampSeconds <= 0) return "--:--:--"
        return timeFormatter.format(Date(timestampSeconds * 1000L))
    }

    fun formatTimeFromMillis(timestampMillis: Long): String {
        if (timestampMillis <= 0) return "--:--:--"
        return timeFormatter.format(Date(timestampMillis))
    }
}
