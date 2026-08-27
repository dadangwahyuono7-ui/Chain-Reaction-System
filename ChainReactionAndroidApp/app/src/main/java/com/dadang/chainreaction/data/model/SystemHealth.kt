package com.dadang.chainreaction.data.model

import com.google.gson.annotations.SerializedName

data class SystemHealth(
    @SerializedName("cpu_pct") val cpuPct: Double = 0.0,
    @SerializedName("memory_pct") val memoryPct: Double = 0.0,
    @SerializedName("disk_pct") val diskPct: Double = 0.0
)
