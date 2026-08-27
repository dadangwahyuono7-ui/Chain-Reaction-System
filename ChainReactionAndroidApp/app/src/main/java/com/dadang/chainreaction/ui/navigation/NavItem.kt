package com.dadang.chainreaction.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.ViewStream
import androidx.compose.ui.graphics.vector.ImageVector

sealed class NavItem(
    val route: String,
    val title: String,
    val icon: ImageVector
) {
    object Command : NavItem("command", "COMMAND", Icons.Default.Dashboard)
    object Bookmap : NavItem("bookmap", "BOOKMAP", Icons.Default.ViewStream)
    object Chain : NavItem("chain", "CHAIN", Icons.Default.Hub)
    object News : NavItem("news", "NEWS", Icons.Default.Article)
    object SystemTab : NavItem("system", "SYSTEM", Icons.Default.Dns)

    companion object {
        val bottomNavItems = listOf(Command, Bookmap, Chain, News, SystemTab)
    }
}

object NavRoutes {
    const val COMMAND = "command"
    const val BOOKMAP = "bookmap"
    const val CHAIN = "chain"
    const val NEWS = "news"
    const val SYSTEM = "system"
    const val NEWS_DETAIL = "news_detail/{itemIndex}"
    const val COMMANDER_HUD = "commander_hud"

    fun newsDetailRoute(index: Int) = "news_detail/$index"
}
