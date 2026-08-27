package com.dadang.chainreaction.ui.navigation

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.dadang.chainreaction.ui.components.TopStatusHeader
import com.dadang.chainreaction.ui.screens.bookmap.BookmapScreen
import com.dadang.chainreaction.ui.screens.chain.ChainScreen
import com.dadang.chainreaction.ui.screens.command.CommandScreen
import com.dadang.chainreaction.ui.screens.command.CommandViewModel
import com.dadang.chainreaction.ui.screens.command.CommanderHudScreen
import com.dadang.chainreaction.ui.screens.news.NewsDetailScreen
import com.dadang.chainreaction.ui.screens.news.NewsScreen
import com.dadang.chainreaction.ui.screens.news.NewsViewModel
import com.dadang.chainreaction.ui.screens.system.SystemScreen
import com.dadang.chainreaction.ui.theme.BgCard
import com.dadang.chainreaction.ui.theme.BgCyberDark
import com.dadang.chainreaction.ui.theme.BorderSubtle
import com.dadang.chainreaction.ui.theme.NeonCyan
import com.dadang.chainreaction.ui.theme.TextMuted
import com.dadang.chainreaction.ui.theme.TextPrimary

@Composable
fun AppNavigation(
    commandViewModel: CommandViewModel = viewModel(),
    newsViewModel: NewsViewModel = viewModel(),
    isKeepScreenOn: Boolean = true,
    onToggleKeepScreenOn: () -> Unit = {}
) {
    val navController = rememberNavController()
    val sultanStatus by commandViewModel.sultanStatus.collectAsState()
    val calendarEvents by commandViewModel.calendarEvents.collectAsState()
    val connectionState by commandViewModel.connectionState.collectAsState()
    val priceDelta by commandViewModel.priceChangeDirection.collectAsState()
    val systemHealth by commandViewModel.systemHealth.collectAsState()

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val isHudMode = currentRoute == NavRoutes.COMMANDER_HUD
    val isNewsDetail = currentRoute?.startsWith("news_detail") == true

    if (isHudMode) {
        CommanderHudScreen(
            status = sultanStatus,
            priceDeltaDirection = priceDelta,
            onClose = { navController.popBackStack() }
        )
        return
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = BgCyberDark,
        topBar = {
            if (!isNewsDetail) {
                TopStatusHeader(
                    connectionState = connectionState,
                    latencyMs = sultanStatus?.dataStatus?.bridgeLatencyMs ?: 0L,
                    eaVersion = sultanStatus?.eaVersion ?: "",
                    isKeepScreenOn = isKeepScreenOn,
                    onToggleKeepScreenOn = onToggleKeepScreenOn,
                    onOpenHudMode = { navController.navigate(NavRoutes.COMMANDER_HUD) },
                    onRefresh = { commandViewModel.refreshAll() }
                )
            }
        },
        bottomBar = {
            if (!isNewsDetail) {
                NavigationBar(
                    containerColor = BgCard,
                    contentColor = TextPrimary,
                    modifier = Modifier.border(BorderStroke(0.8.dp, BorderSubtle))
                ) {
                    NavItem.bottomNavItems.forEach { item ->
                        val isSelected = currentRoute == item.route
                        NavigationBarItem(
                            selected = isSelected,
                            onClick = {
                                navController.navigate(item.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = {
                                Icon(
                                    imageVector = item.icon,
                                    contentDescription = item.title,
                                    modifier = Modifier.size(20.dp)
                                )
                            },
                            label = {
                                Text(
                                    text = item.title,
                                    fontSize = 9.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                    fontFamily = FontFamily.Monospace
                                )
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = NeonCyan,
                                selectedTextColor = NeonCyan,
                                indicatorColor = NeonCyan.copy(alpha = 0.15f),
                                unselectedIconColor = TextMuted,
                                unselectedTextColor = TextMuted
                            )
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = NavRoutes.COMMAND,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(NavRoutes.COMMAND) {
                CommandScreen(
                    status = sultanStatus,
                    calendarEvents = calendarEvents,
                    priceDeltaDirection = priceDelta
                )
            }

            composable(NavRoutes.BOOKMAP) {
                BookmapScreen(status = sultanStatus)
            }

            composable(NavRoutes.CHAIN) {
                ChainScreen(status = sultanStatus)
            }

            composable(NavRoutes.NEWS) {
                NewsScreen(
                    viewModel = newsViewModel,
                    onNavigateToDetail = { index ->
                        navController.navigate(NavRoutes.newsDetailRoute(index))
                    }
                )
            }

            composable(NavRoutes.SYSTEM) {
                SystemScreen(
                    status = sultanStatus,
                    health = systemHealth
                )
            }

            composable(
                route = NavRoutes.NEWS_DETAIL,
                arguments = listOf(navArgument("itemIndex") { type = NavType.IntType })
            ) { backStackEntry ->
                val index = backStackEntry.arguments?.getInt("itemIndex") ?: 0
                val item = newsViewModel.getNewsItemByIndex(index)
                NewsDetailScreen(
                    item = item,
                    sultanStatus = sultanStatus,
                    onNavigateBack = { navController.popBackStack() }
                )
            }

            composable(NavRoutes.COMMANDER_HUD) {
                CommanderHudScreen(
                    status = sultanStatus,
                    priceDeltaDirection = priceDelta,
                    onClose = { navController.popBackStack() }
                )
            }
        }
    }
}
