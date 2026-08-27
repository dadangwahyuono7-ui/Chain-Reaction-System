package com.dadang.chainreaction.data.model

import com.google.gson.annotations.SerializedName

data class SultanStatus(
    val timestamp: Long = 0L,
    val online: Boolean = false,
    val symbol: String = "XAUUSD",
    val price: Double = 0.0,
    val balance: Double = 0.0,
    val equity: Double = 0.0,
    @SerializedName("ea_version") val eaVersion: String = "",
    val regime: RegimeInfo = RegimeInfo(),
    val flow: FlowInfo = FlowInfo(),
    val liquidity: LiquidityInfo = LiquidityInfo(),
    @SerializedName("wall_sweep") val wallSweep: WallSweepInfo = WallSweepInfo(),
    val usd: UsdInfo = UsdInfo(),
    val conviction: ConvictionInfo = ConvictionInfo(),
    @SerializedName("bookmap_read") val bookmapRead: BookmapReadInfo = BookmapReadInfo(),
    val location: LocationInfo = LocationInfo(),
    val context: ContextInfo = ContextInfo(),
    val signals: SignalsInfo = SignalsInfo(),
    @SerializedName("data_status") val dataStatus: DataStatusInfo = DataStatusInfo(),
    @SerializedName("sd_zones") val sdZones: SdZonesInfo? = null,
    @SerializedName("confluence_radar") val confluenceRadar: ConfluenceRadarInfo? = null
)

data class RegimeInfo(
    val d1: String = "WAIT",
    val h4: String = "WAIT",
    val h1: String = "WAIT",
    val m30: String = "WAIT",
    val m15: String = "WAIT",
    val m5: String = "WAIT",
    val m1: String = "WAIT",
    @SerializedName("alignment_pct") val alignmentPct: Double = 0.0,
    val regime: String = "UNKNOWN",
    @SerializedName("htf_bias") val htfBias: String = "UNKNOWN",
    @SerializedName("m5_status") val m5Status: String = "UNKNOWN"
)

data class FlowInfo(
    val cvd: Double = 0.0,
    @SerializedName("delta_1m") val delta1m: Double = 0.0,
    @SerializedName("delta_history") val deltaHistory: List<Double> = emptyList(),
    @SerializedName("vol_ratio_buy_pct") val volRatioBuyPct: Double = 50.0,
    @SerializedName("pulse_pct") val pulsePct: Double = 0.0,
    val absorption: String = "NONE",
    @SerializedName("flow_dominant") val flowDominant: String = "NONE"
)

data class LiquidityInfo(
    @SerializedName("bid_wall_price") val bidWallPrice: Double = 0.0,
    @SerializedName("bid_wall_size") val bidWallSize: Double = 0.0,
    @SerializedName("bid_wall_ratio") val bidWallRatio: Double = 0.0,
    @SerializedName("ask_wall_price") val askWallPrice: Double = 0.0,
    @SerializedName("ask_wall_size") val askWallSize: Double = 0.0,
    @SerializedName("ask_wall_ratio") val askWallRatio: Double = 0.0,
    @SerializedName("nearest_wall_side") val nearestWallSide: String = "NONE",
    @SerializedName("nearest_wall_distance") val nearestWallDistance: Double = 0.0,
    @SerializedName("wall_imbalance") val wallImbalance: Double = 0.0,
    @SerializedName("bid_wall_count") val bidWallCount: Int = 0,
    @SerializedName("ask_wall_count") val askWallCount: Int = 0,
    @SerializedName("bid_wall_total_lot") val bidWallTotalLot: Double = 0.0,
    @SerializedName("ask_wall_total_lot") val askWallTotalLot: Double = 0.0,
    @SerializedName("bid_ladder") val bidLadder: List<List<Double>> = emptyList(),
    @SerializedName("ask_ladder") val askLadder: List<List<Double>> = emptyList()
)

data class WallSweepInfo(
    val active: Boolean = false,
    val side: String = "",
    val price: Double = 0.0,
    val size: Double = 0.0,
    val status: String = "NONE",
    @SerializedName("since_sec") val sinceSec: Long = 0L
)

data class UsdInfo(
    val symbol: String = "DXY",
    val dir: String = "-",
    val bias: String = "-",
    @SerializedName("gold_effect") val goldEffect: String = "-",
    @SerializedName("next_event") val nextEvent: String = "-",
    @SerializedName("next_mins") val nextMins: Long = 0L
)

data class ConvictionInfo(
    val dir: String = "-",
    val mode: String = "-",
    val score: Int = 0,
    val max: Int = 6,
    val grade: String = "-",
    @SerializedName("chain_done") val chainDone: String = "-",
    @SerializedName("chain_next") val chainNext: String = "-",
    @SerializedName("chain_pending") val chainPending: String = "-",
    @SerializedName("flow_score") val flowScore: Int = 0,
    @SerializedName("flow_max") val flowMax: Int = 6,
    val against: List<String> = emptyList()
)

data class BookmapReadInfo(
    val wall: String = "-",
    val cvd: String = "-",
    val absorption: String = "-",
    val iceberg: String = "-",
    val location: String = "-",
    val verdict: String = "-",
    @SerializedName("iceberg_bid_px") val icebergBidPx: Double = 0.0,
    @SerializedName("iceberg_ask_px") val icebergAskPx: Double = 0.0
)

data class LocationInfo(
    val poc: Double = 0.0,
    @SerializedName("val") val valPrice: Double = 0.0,
    @SerializedName("vah") val vahPrice: Double = 0.0,
    @SerializedName("current_price") val currentPrice: Double = 0.0,
    val position: String = "INSIDE_VA",
    @SerializedName("distance_to_poc") val distanceToPoc: Double = 0.0,
    @SerializedName("distance_to_poc_pct") val distanceToPocPct: Double = 0.0,
    @SerializedName("va_bias") val vaBias: String = "-",
    @SerializedName("range_24h") val range24h: Double = 0.0,
    val atr14: Double = 0.0
)

data class ContextInfo(
    @SerializedName("htf_bias") val htfBias: String = "UNKNOWN",
    val flow: String = "UNKNOWN",
    val liquidity: String = "UNKNOWN",
    val location: String = "UNKNOWN",
    val regime: String = "UNKNOWN",
    val action: String = "WAIT_OBSERVE"
)

data class SignalsInfo(
    @SerializedName("barrier_warning") val barrierWarning: String? = null,
    @SerializedName("momentum_m5") val momentumM5: MomentumSignal? = null,
    @SerializedName("momentum_m5_bookmap") val momentumM5Bookmap: MomentumSignal? = null,
    @SerializedName("momentum_m5_footprint") val momentumM5Footprint: MomentumSignal? = null,
    @SerializedName("chain_signal") val chainSignal: ChainSignal? = null,
    @SerializedName("cvd_divergence") val cvdDivergence: CvdDivergenceSignal? = null,
    val ivb: IvbSignal? = null,
    @SerializedName("volume_node") val volumeNode: TextSignal? = null,
    val countdown: CountdownInfo = CountdownInfo()
)

data class MomentumSignal(
    val text: String = "",
    val dir: String = ""
)

data class ChainSignal(
    val layer: Int = 0,
    val dir: String = ""
)

data class CvdDivergenceSignal(
    val text: String = "",
    val status: String = ""
)

data class IvbSignal(
    val text: String = "",
    val locked: Boolean = false
)

data class TextSignal(
    val text: String = ""
)

data class CountdownInfo(
    val h4: Long = 0L,
    val h1: Long = 0L,
    val m30: Long = 0L,
    val m15: Long = 0L,
    val m5: Long = 0L,
    val m1: Long = 0L
)

data class DataStatusInfo(
    @SerializedName("bookmap_online") val bookmapOnline: Boolean = false,
    @SerializedName("bridge_latency_ms") val bridgeLatencyMs: Long = 0L
)

data class SdZonesInfo(
    val available: Boolean = false,
    val zones: List<SdZone> = emptyList(),
    val roadmap: SdRoadmap = SdRoadmap(),
    val decision: SdDecision = SdDecision(),
    @SerializedName("break") val breakStatus: SdBreak = SdBreak()
)

data class SdZone(
    val side: String = "",
    val lo: Double = 0.0,
    val hi: Double = 0.0,
    @SerializedName("wall_count") val wallCount: Int = 0,
    @SerializedName("total_lot") val totalLot: Double = 0.0,
    val status: String = "",
    val strength: String = "",
    @SerializedName("retest_count") val retestCount: Int = 0,
    @SerializedName("absorption_hits") val absorptionHits: Int = 0,
    val score: Int = 0
)

data class SdRoadmap(
    val supply: List<SdZone> = emptyList(),
    val demand: List<SdZone> = emptyList()
)

data class SdDecision(
    val location: String = "",
    @SerializedName("location_text") val locationText: String = "",
    @SerializedName("market_state") val marketState: String = "",
    val setup: String = "",
    @SerializedName("reason_text") val reasonText: String = "",
    val focus: String = "",
    @SerializedName("buyer_pct") val buyerPct: Int = 0,
    @SerializedName("seller_pct") val sellerPct: Int = 0,
    val compression: Boolean = false
)

data class SdBreak(
    @SerializedName("supply_state") val supplyState: String = "",
    @SerializedName("supply_momentum") val supplyMomentum: String = "",
    @SerializedName("demand_state") val demandState: String = "",
    @SerializedName("demand_momentum") val demandMomentum: String = "",
    @SerializedName("market_read") val marketRead: String = "",
    val direction: String = "",
    @SerializedName("status_text") val statusText: String = "",
    @SerializedName("no_trade_zone") val noTradeZone: Boolean = false
)


data class ConfluenceRadarInfo(
    val dir: String = "WAIT",
    val score: Int = 0,
    val max: Int = 5,
    val pct: Double = 0.0,
    val grade: String = "-",
    val mode: String = "-",
    val action: String = "-"
)
