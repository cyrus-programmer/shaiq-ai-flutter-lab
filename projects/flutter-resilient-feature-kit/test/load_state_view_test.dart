import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:resilient_feature_kit/resilient_feature_kit.dart';

Widget subject(LoadState<List<String>> state, {VoidCallback? onRetry}) => MaterialApp(
      home: Scaffold(
        body: LoadStateView<List<String>>(
          state: state,
          onRetry: onRetry ?? () {},
          isEmpty: (List<String> data) => data.isEmpty,
          dataBuilder: (_, List<String> data) => Text(data.join(',')),
        ),
      ),
    );

void main() {
  testWidgets('shows progress for first load', (WidgetTester tester) async {
    await tester.pumpWidget(subject(const LoadInProgress<List<String>>()));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('shows empty state', (WidgetTester tester) async {
    await tester.pumpWidget(subject(const LoadSuccess<List<String>>(<String>[])));
    expect(find.text('Nothing here yet.'), findsOneWidget);
  });

  testWidgets('shows data and stale status together', (WidgetTester tester) async {
    await tester.pumpWidget(subject(const LoadSuccess<List<String>>(<String>['saved'], isStale: true)));
    expect(find.text('saved'), findsOneWidget);
    expect(find.text('Showing saved data'), findsOneWidget);
  });

  testWidgets('keeps previous data visible during refresh', (WidgetTester tester) async {
    await tester.pumpWidget(subject(const LoadInProgress<List<String>>(previous: <String>['cached'])));
    expect(find.text('cached'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('invokes retry from terminal error state', (WidgetTester tester) async {
    int retries = 0;
    await tester.pumpWidget(subject(
      LoadFailure<List<String>>(StateError('offline'), StackTrace.empty),
      onRetry: () => retries += 1,
    ));
    expect(find.text('Unable to load data'), findsOneWidget);
    await tester.tap(find.text('Try again'));
    expect(retries, 1);
  });

  testWidgets('keeps data when refresh fails', (WidgetTester tester) async {
    await tester.pumpWidget(subject(
      LoadFailure<List<String>>(
        StateError('offline'),
        StackTrace.empty,
        previous: const <String>['cached'],
      ),
    ));
    expect(find.text('cached'), findsOneWidget);
    expect(find.text('Could not refresh. Showing saved data.'), findsOneWidget);
  });
}
