import 'package:aria_studio/app.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'state/aria_controller.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = true;
  final controller = AriaController();
  await controller.loadPersistedSettings();
  runApp(
    ChangeNotifierProvider.value(
      value: controller,
      child: const AriaStudioApp(),
    ),
  );
}
