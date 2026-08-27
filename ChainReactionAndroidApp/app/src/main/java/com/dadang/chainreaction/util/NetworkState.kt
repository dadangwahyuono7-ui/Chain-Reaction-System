package com.dadang.chainreaction.util

enum class ConnectionState {
    CONNECTED,
    RECONNECTING,
    DISCONNECTED
}

data class SystemStatusState(
    val connectionState: ConnectionState = ConnectionState.CONNECTED,
    val lastUpdatedMillis: Long = System.currentTimeMillis(),
    val errorMessage: String? = null,
    val isKeepAliveActive: Boolean = false
)
