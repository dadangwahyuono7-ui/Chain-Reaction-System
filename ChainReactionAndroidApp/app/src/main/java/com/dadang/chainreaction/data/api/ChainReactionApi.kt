package com.dadang.chainreaction.data.api

import com.dadang.chainreaction.data.model.CalendarEvent
import com.dadang.chainreaction.data.model.NewsFeed
import com.dadang.chainreaction.data.model.SultanStatus
import com.dadang.chainreaction.data.model.SystemHealth
import retrofit2.http.GET

interface ChainReactionApi {

    @GET("sultan_status.json")
    suspend fun getSultanStatus(): SultanStatus

    @GET("news_feed.json")
    suspend fun getNewsFeed(): NewsFeed

    @GET("ff_calendar.json")
    suspend fun getCalendar(): List<CalendarEvent>

    @GET("api/system_health")
    suspend fun getSystemHealth(): SystemHealth
}
