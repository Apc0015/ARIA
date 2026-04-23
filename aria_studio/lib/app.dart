// ARIA Studio — application root & routing shell
// Routes: /login → /home (Dashboard) → /settings

import 'package:flutter/material.dart';

import 'pages/dashboard_page.dart';
import 'pages/history_page.dart';
import 'pages/login_page.dart';
import 'pages/reports_page.dart';
import 'pages/run_detail_page.dart';
import 'pages/settings_page.dart';
import 'pages/setup_page.dart';
import 'theme/aria_theme.dart';
import 'widgets/effects_3d.dart';

class AriaStudioApp extends StatelessWidget {
  const AriaStudioApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      // Root-level cursor ensures OS cursor is always visible
      // even in gaps between child MouseRegion widgets.
      cursor: SystemMouseCursors.basic,
      child: MaterialApp(
        title: 'ARIA Studio',
        debugShowCheckedModeBanner: false,
        theme: AriaTheme.dark(),
        initialRoute: '/setup',
        onGenerateRoute: (settings) {
          Widget page;
          switch (settings.name) {
            case '/setup':
              page = const SetupPage();
            case '/home':
              page = const DashboardPage();
            case '/settings':
              page = const SettingsPage();
            case '/history':
              page = const HistoryPage();
            case '/login':
              page = const LoginPage();
            case '/run-detail':
              page = RunDetailPage(runId: settings.arguments as String? ?? '');
            case '/reports':
              page = ReportsPage(runId: settings.arguments as String? ?? '');
            default:
              page = const SetupPage();
          }
          // 3D cube page transition
          return Aria3dPageRoute(page: page, settings: settings);
        },
      ),
    );
  }
}
