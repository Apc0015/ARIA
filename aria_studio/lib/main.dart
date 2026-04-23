import 'package:aria_studio/app.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'state/aria_controller.dart';

void main() {
  GoogleFonts.config.allowRuntimeFetching = true;
  runApp(
    ChangeNotifierProvider(
      create: (_) => AriaController()..bootstrap(),
      child: const AriaStudioApp(),
    ),
  );
}
