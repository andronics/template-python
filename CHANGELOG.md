# Changelog

## [2.4.0](https://github.com/andronics/template-python/compare/v2.3.4...v2.4.0) (2026-11-03)


### ✨ Features

* a lifespan with background threads, and /readyz 503 when one dies ([#36](https://github.com/andronics/template-python/issues/36)) ([332e9df](https://github.com/andronics/template-python/commit/332e9df20ff67ff1f7c5b573ef40e71f1a96eaa9))
* a Prometheus /metrics endpoint on interpose's registry ([#38](https://github.com/andronics/template-python/issues/38)) ([f5d0bb6](https://github.com/andronics/template-python/commit/f5d0bb62cd988b047241800e2455d4060479dfaf))
* commit docs/openapi.json and fail CI when it drifts or breaks undeclared ([#35](https://github.com/andronics/template-python/issues/35)) ([449ee36](https://github.com/andronics/template-python/commit/449ee36427021e93008df871130651348cc4fca5))


### 📚 Documentation

* one uvicorn process per pod, scale by replicas, a singleton scheduler ([#39](https://github.com/andronics/template-python/issues/39)) ([642df6c](https://github.com/andronics/template-python/commit/642df6c062eee0a067cf73ea403cb394f37f9092))

## [2.3.4](https://github.com/andronics/template-python/compare/v2.3.3...v2.3.4) (2026-11-02)


### 🐛 Bug Fixes

* the PR template asks whether a PR was generated, not by what ([#29](https://github.com/andronics/template-python/issues/29)) ([43f3241](https://github.com/andronics/template-python/commit/43f324122b3fedb1527795a7459ce6a4a1edb711))

## [2.3.3](https://github.com/andronics/template-python/compare/v2.3.2...v2.3.3) (2026-11-02)


### 🐛 Bug Fixes

* the design-record template asks for people only as authors ([#27](https://github.com/andronics/template-python/issues/27)) ([ea9683d](https://github.com/andronics/template-python/commit/ea9683d197e4332bba78c06fec686e0449cd91d3))

## [2.3.2](https://github.com/andronics/template-python/compare/v2.3.1...v2.3.2) (2026-11-02)


### 📚 Documentation

* migrating a project with no template history ([#25](https://github.com/andronics/template-python/issues/25)) ([613524d](https://github.com/andronics/template-python/commit/613524d7d9dfc3ce4fb747de9108e378e3b16b02))

## [2.3.1](https://github.com/andronics/template-python/compare/v2.3.0...v2.3.1) (2026-11-02)


### 📚 Documentation

* record FastAPI as the only web framework for services (0004) ([#23](https://github.com/andronics/template-python/issues/23)) ([47e893a](https://github.com/andronics/template-python/commit/47e893a82d1a4f61a04c9914a384da7ee63ff940))

## [2.3.0](https://github.com/andronics/template-python/compare/v2.2.0...v2.3.0) (2026-11-02)


### ✨ Features

* generated config.py on interpose v0.2.0's typed accessors ([#20](https://github.com/andronics/template-python/issues/20)) ([556e84b](https://github.com/andronics/template-python/commit/556e84b4ede93941354a836661df5b335bda236d))

## [2.2.0](https://github.com/andronics/template-python/compare/v2.1.0...v2.2.0) (2026-11-02)


### ✨ Features

* generated config.py on interpose (0003) ([#18](https://github.com/andronics/template-python/issues/18)) ([b7a0ce4](https://github.com/andronics/template-python/commit/b7a0ce4090251e3cace3fc8124d89d97567ec2f6))

## [2.1.0](https://github.com/andronics/template-python/compare/v2.0.4...v2.1.0) (2026-11-02)


### ✨ Features

* a scheduled tag-check workflow for git-tag-pinned dependencies (0002) ([#14](https://github.com/andronics/template-python/issues/14)) ([8f9c8c6](https://github.com/andronics/template-python/commit/8f9c8c62886390118008e70f4a9ab9918440c6eb))

## [2.0.4](https://github.com/andronics/template-python/compare/v2.0.3...v2.0.4) (2026-11-02)


### 📚 Documentation

* record what the first interpose consumers showed (0003) ([#15](https://github.com/andronics/template-python/issues/15)) ([eb3a5bb](https://github.com/andronics/template-python/commit/eb3a5bbb1c9db6da3f7ee6065d51fe108500fabb))

## [2.0.3](https://github.com/andronics/template-python/compare/v2.0.2...v2.0.3) (2026-11-02)


### 📚 Documentation

* propose interpose config and a tag-check workflow ([#12](https://github.com/andronics/template-python/issues/12)) ([3dfbecd](https://github.com/andronics/template-python/commit/3dfbecd82b6a81b51549a837208663f4e87c6a7e))

## [2.0.2](https://github.com/andronics/template-python/compare/v2.0.1...v2.0.2) (2026-11-02)


### 📚 Documentation

* migration scratch off /tmp, and interpose has no container overlay ([#9](https://github.com/andronics/template-python/issues/9)) ([ddf46b0](https://github.com/andronics/template-python/commit/ddf46b0e0dcad648ee50c8c3e7284532b85e3c6c))

## [2.0.1](https://github.com/andronics/template-python/compare/v2.0.0...v2.0.1) (2026-11-02)


### 📚 Documentation

* point the migration prompts at the v2.x releases ([#6](https://github.com/andronics/template-python/issues/6)) ([a797e77](https://github.com/andronics/template-python/commit/a797e77b424d8e788be8757eee2bf9a3cb8c724f))

## [2.0.0](https://github.com/andronics/template-python/compare/v1.0.0...v2.0.0) (2026-11-02)


### ⚠ BREAKING CHANGES

* require template-base v2.0.0 ([#1](https://github.com/andronics/template-python/issues/1))

### ✨ Features

* require template-base v2.0.0 ([#1](https://github.com/andronics/template-python/issues/1)) ([9fe6c5a](https://github.com/andronics/template-python/commit/9fe6c5ad80c5af2b6de58e7ddf34f01122c719fd))


### 🐛 Bug Fixes

* pin astral-sh/setup-uv v10.3.3 ([#3](https://github.com/andronics/template-python/issues/3)) ([ea93f60](https://github.com/andronics/template-python/commit/ea93f60ed91513b0e957c32c0fcf9f529d515dde))
* tell new projects to fill .github/repository.toml, and align the hadolint pin ([#4](https://github.com/andronics/template-python/issues/4)) ([6be89b8](https://github.com/andronics/template-python/commit/6be89b850602bc1d96a6a8a0cbed05a7b104e8da))
