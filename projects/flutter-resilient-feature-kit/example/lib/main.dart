import 'dart:async';

import 'package:flutter/material.dart';
import 'package:resilient_feature_kit/resilient_feature_kit.dart';

void main() => runApp(const DemoApp());

final class DemoApp extends StatelessWidget {
  const DemoApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Resilient Feature Kit',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF3156D3)),
          useMaterial3: true,
        ),
        home: const CatalogueScreen(),
      );
}

final class Product {
  const Product(this.name, this.status);
  final String name;
  final String status;
}

final class DemoRepository {
  bool failNext = false;
  int requestCount = 0;

  Future<List<Product>> fetch() async {
    requestCount += 1;
    await Future<void>.delayed(const Duration(milliseconds: 700));
    if (failNext) {
      failNext = false;
      throw const FormatException('Simulated service failure');
    }
    return const <Product>[
      Product('Checkout API', 'Healthy'),
      Product('Mobile sync', 'Healthy'),
      Product('Notification worker', 'Degraded'),
    ];
  }
}

final class CatalogueScreen extends StatefulWidget {
  const CatalogueScreen({super.key});

  @override
  State<CatalogueScreen> createState() => _CatalogueScreenState();
}

final class _CatalogueScreenState extends State<CatalogueScreen> {
  late final DemoRepository _repository;
  late final QueryController<List<Product>> _controller;

  @override
  void initState() {
    super.initState();
    _repository = DemoRepository();
    _controller = QueryController<List<Product>>(
      fetcher: _repository.fetch,
      cacheKey: 'service-catalogue',
      cacheStore: MemoryCacheStore(),
      cacheTimeToLive: const Duration(seconds: 10),
      retryPolicy: const RetryPolicy(maxAttempts: 1),
    )..addListener(_rebuild);
    unawaited(_controller.load());
  }

  void _rebuild() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _controller
      ..removeListener(_rebuild)
      ..dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Service catalogue'),
          actions: <Widget>[
            IconButton(
              tooltip: 'Simulate failed refresh',
              onPressed: () {
                _repository.failNext = true;
                unawaited(_controller.refresh());
              },
              icon: const Icon(Icons.cloud_off_outlined),
            ),
            IconButton(
              tooltip: 'Refresh',
              onPressed: () => unawaited(_controller.refresh()),
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: LoadStateView<List<Product>>(
          state: _controller.state,
          onRetry: () => unawaited(_controller.refresh()),
          isEmpty: (List<Product> products) => products.isEmpty,
          dataBuilder: (BuildContext context, List<Product> products) =>
              RefreshIndicator(
            onRefresh: _controller.refresh,
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
              itemCount: products.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (BuildContext context, int index) {
                final Product product = products[index];
                final bool healthy = product.status == 'Healthy';
                return Card(
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: healthy
                          ? Colors.green.shade100
                          : Colors.orange.shade100,
                      child: Icon(
                        healthy ? Icons.check : Icons.warning_amber,
                        color: healthy ? Colors.green.shade800 : Colors.orange.shade900,
                      ),
                    ),
                    title: Text(product.name),
                    subtitle: Text(product.status),
                  ),
                );
              },
            ),
          ),
        ),
      );
}
