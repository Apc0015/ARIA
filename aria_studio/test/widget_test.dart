import 'package:aria_studio/app.dart';
import 'package:aria_studio/state/aria_controller.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('ARIA Studio renders shell', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AriaController(),
        child: const AriaStudioApp(),
      ),
    );

    expect(find.text('ARIA Studio'), findsOneWidget);
    expect(find.text('Mission Editor'), findsOneWidget);
  });
}
