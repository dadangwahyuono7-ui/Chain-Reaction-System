package com.dadang.chainreaction.ui.screens.news

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.NewsFeed
import com.dadang.chainreaction.data.model.NewsItem
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.repository.TradingRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn

class NewsViewModel : ViewModel() {

    private val repository = TradingRepository.getInstance()

    val sultanStatus: StateFlow<SultanStatus?> = repository.sultanStatus
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val newsFeed: StateFlow<NewsFeed?> = repository.newsFeed
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    val calendarEvents: StateFlow<List<CalendarEvent>> = repository.calendarEvents
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    private val _selectedImpactFilter = MutableStateFlow("ALL")
    val selectedImpactFilter: StateFlow<String> = _selectedImpactFilter.asStateFlow()

    fun setImpactFilter(filter: String) {
        _selectedImpactFilter.value = filter
    }

    fun getNewsItemByIndex(index: Int): NewsItem? {
        val items = newsFeed.value?.items ?: return null
        return if (index in items.indices) items[index] else null
    }
}
