package com.dadang.chainreaction.data.repository

import com.dadang.chainreaction.data.api.ApiClient
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.NewsFeed
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.SystemHealth
import com.dadang.chainreaction.util.ConnectionState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class TradingRepository private constructor() {

    private val api = ApiClient.api

    private val _sultanStatus = MutableStateFlow<SultanStatus?>(null)
    val sultanStatus: StateFlow<SultanStatus?> = _sultanStatus.asStateFlow()

    private val _newsFeed = MutableStateFlow<NewsFeed?>(null)
    val newsFeed: StateFlow<NewsFeed?> = _newsFeed.asStateFlow()

    private val _calendarEvents = MutableStateFlow<List<CalendarEvent>>(emptyList())
    val calendarEvents: StateFlow<List<CalendarEvent>> = _calendarEvents.asStateFlow()

    private val _systemHealth = MutableStateFlow<SystemHealth?>(null)
    val systemHealth: StateFlow<SystemHealth?> = _systemHealth.asStateFlow()

    private val _connectionState = MutableStateFlow(ConnectionState.CONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _lastSuccessfulFetch = MutableStateFlow(System.currentTimeMillis())
    val lastSuccessfulFetch: StateFlow<Long> = _lastSuccessfulFetch.asStateFlow()

    // 1 for Up (Green flash), -1 for Down (Red flash), 0 for Same
    private val _priceChangeDirection = MutableStateFlow(0)
    val priceChangeDirection: StateFlow<Int> = _priceChangeDirection.asStateFlow()

    private var sultanJob: Job? = null
    private var newsJob: Job? = null
    private var calendarJob: Job? = null
    private var healthJob: Job? = null
    private var scope: CoroutineScope? = null

    private var previousPrice: Double = 0.0
    private var consecutiveErrors = 0

    fun startPolling(externalScope: CoroutineScope) {
        if (sultanJob?.isActive == true) return
        scope = externalScope

        startSultanPolling(externalScope)
        startNewsPolling(externalScope)
        startCalendarPolling(externalScope)
        startHealthPolling(externalScope)
    }

    private fun startSultanPolling(scope: CoroutineScope) {
        sultanJob?.cancel()
        sultanJob = scope.launch(Dispatchers.IO) {
            while (isActive) {
                try {
                    val status = api.getSultanStatus()
                    
                    // Track price delta for visual flash
                    val newPrice = status.price
                    if (previousPrice > 0.0 && newPrice != previousPrice) {
                        _priceChangeDirection.value = if (newPrice > previousPrice) 1 else -1
                    }
                    previousPrice = newPrice

                    _sultanStatus.value = status
                    _connectionState.value = ConnectionState.CONNECTED
                    _lastSuccessfulFetch.value = System.currentTimeMillis()
                    consecutiveErrors = 0
                } catch (e: Exception) {
                    consecutiveErrors++
                    if (consecutiveErrors >= 3) {
                        _connectionState.value = ConnectionState.DISCONNECTED
                    } else {
                        _connectionState.value = ConnectionState.RECONNECTING
                    }
                }
                delay(1000)
            }
        }
    }

    private fun startNewsPolling(scope: CoroutineScope) {
        newsJob?.cancel()
        newsJob = scope.launch(Dispatchers.IO) {
            while (isActive) {
                try {
                    val news = api.getNewsFeed()
                    _newsFeed.value = news
                } catch (_: Exception) {
                    // Retains existing news state on failure
                }
                delay(60_000)
            }
        }
    }

    private fun startCalendarPolling(scope: CoroutineScope) {
        calendarJob?.cancel()
        calendarJob = scope.launch(Dispatchers.IO) {
            while (isActive) {
                try {
                    val events = api.getCalendar()
                    _calendarEvents.value = events
                } catch (_: Exception) {
                    // Retains existing calendar state on failure
                }
                delay(60_000)
            }
        }
    }

    private fun startHealthPolling(scope: CoroutineScope) {
        healthJob?.cancel()
        healthJob = scope.launch(Dispatchers.IO) {
            while (isActive) {
                try {
                    val health = api.getSystemHealth()
                    _systemHealth.value = health
                } catch (_: Exception) {
                    // Retains existing health state on failure
                }
                delay(5_000)
            }
        }
    }

    fun stopPolling() {
        sultanJob?.cancel()
        newsJob?.cancel()
        calendarJob?.cancel()
        healthJob?.cancel()
        sultanJob = null
        newsJob = null
        calendarJob = null
        healthJob = null
    }

    fun triggerManualRefresh() {
        scope?.let { currentScope ->
            currentScope.launch(Dispatchers.IO) {
                try {
                    _sultanStatus.value = api.getSultanStatus()
                    _newsFeed.value = api.getNewsFeed()
                    _calendarEvents.value = api.getCalendar()
                    _systemHealth.value = api.getSystemHealth()
                    _connectionState.value = ConnectionState.CONNECTED
                    _lastSuccessfulFetch.value = System.currentTimeMillis()
                } catch (_: Exception) {
                    _connectionState.value = ConnectionState.RECONNECTING
                }
            }
        }
    }

    companion object {
        @Volatile
        private var instance: TradingRepository? = null

        fun getInstance(): TradingRepository {
            return instance ?: synchronized(this) {
                instance ?: TradingRepository().also { instance = it }
            }
        }
    }
}
