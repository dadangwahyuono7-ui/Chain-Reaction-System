package com.dadang.chainreaction.ui.screens.command

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.NewsFeed
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.SystemHealth
import com.dadang.chainreaction.data.repository.TradingRepository
import com.dadang.chainreaction.util.ConnectionState
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class CommandViewModel : ViewModel() {

    private val repository = TradingRepository.getInstance()

    val sultanStatus: StateFlow<SultanStatus?> = repository.sultanStatus
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val connectionState: StateFlow<ConnectionState> = repository.connectionState
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ConnectionState.CONNECTED)

    val priceChangeDirection: StateFlow<Int> = repository.priceChangeDirection
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    val newsFeed: StateFlow<NewsFeed?> = repository.newsFeed
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val calendarEvents: StateFlow<List<CalendarEvent>> = repository.calendarEvents
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val systemHealth: StateFlow<SystemHealth?> = repository.systemHealth
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun refreshAll() {
        repository.triggerManualRefresh()
    }
}
