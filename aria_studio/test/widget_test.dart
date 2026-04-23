import 'package:aria_studio/app.dart';
import 'package:aria_studio/state/aria_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('App renders MaterialApp without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AriaController(),
        child: const AriaStudioApp(),
      ),
    );
    await tester.pump();
    expect(find.byType(MaterialApp), findsOneWidget);
  });

  testWidgets('App renders at least one Text widget on initial page', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AriaController(),
        child: const AriaStudioApp(),
      ),
    );
    await tester.pump();
    // The initial page (SetupPage or DashboardPage) renders text
    expect(find.byType(Text), findsWidgets);
  });
}
