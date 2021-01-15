# Changelog

<!--next-version-placeholder-->

## v0.11.1 (2021-01-12)
### Fix
* Debug the printing feature of the `sw go` ([`888fb78`](https://github.com/kalekundert/stepwise/commit/888fb7836330b2d9b15adab27f7122327734816d))

## v0.11.0 (2021-01-11)
### Feature
* Migrate to appcli ([`ac5f6f9`](https://github.com/kalekundert/stepwise/commit/ac5f6f9d1efbb61ad4e7d4b523204e350d47a207))

### Fix
* Ignore extraneous openpyxl and pandas warnings ([`bbb7f55`](https://github.com/kalekundert/stepwise/commit/bbb7f55ab2b0711113fa7750285d334a2758a213))
* Check the header before attempting to unpickle a byte stream ([`8bb1cf9`](https://github.com/kalekundert/stepwise/commit/8bb1cf99cb6e8f2f89a1344890c23d89205d5fb4))

## v0.10.0 (2020-12-22)
### Feature
* Migrate configuration to appcli ([`403eece`](https://github.com/kalekundert/stepwise/commit/403eeceda0645cd638d58258aae79e8e5a8ff6ed))
* Add sorthand symbols to the reaction command ([`0bc08a0`](https://github.com/kalekundert/stepwise/commit/0bc08a08106e77a7c817b721aa99bb4fce70de8b))

### Fix
* Don't require `lpstat` to be installed ([`66b3c62`](https://github.com/kalekundert/stepwise/commit/66b3c6248373dc79a0d05a65b83e139375cb4612))
* Handle unexpected `lpstat -d` output ([`47fcbc0`](https://github.com/kalekundert/stepwise/commit/47fcbc02bae4b32d4234bd4bbec170c348cdf085))
* Improve the Footnote comparison operators ([`4dc188a`](https://github.com/kalekundert/stepwise/commit/4dc188a5530527d793f2ae14a31f404fe151f7c4))

## v0.9.0 (2020-11-03)
### Feature
* Add an accessor for the current step of a protocol ([`72c7d19`](https://github.com/kalekundert/stepwise/commit/72c7d19c2c5052005c093d295695607dc9dcefb9))

## v0.8.0 (2020-11-03)
### Feature
* Add function to print protocols as pickles ([`587792c`](https://github.com/kalekundert/stepwise/commit/587792c5835bf614afda2fddc7336389359bec46))

### Fix
* Allow MasterMix objects to be pickled ([`3d9dd35`](https://github.com/kalekundert/stepwise/commit/3d9dd355eabce997060896489845e588787104a5))

## v0.7.3 (2020-11-03)
### Fix
* Handle SystemExit return codes that are strings ([`9ab5357`](https://github.com/kalekundert/stepwise/commit/9ab53571b66857d5cf6fc5572d999e4b1e04cedc))

## v0.7.2 (2020-11-02)
### Fix
* Support the range syntax when pruning footnotes ([`790b6f2`](https://github.com/kalekundert/stepwise/commit/790b6f217908f89bc329f5526dc8c3c0923d2203))

## v0.7.1 (2020-11-02)
### Fix
* Ensure that return codes are always integers ([`5cd681e`](https://github.com/kalekundert/stepwise/commit/5cd681e7c38948b6b1d00f9207bbba13b6bd8a9d))

## v0.7.0 (2020-11-01)
### Feature
* Rename the `custom` builtin protocol to `step` ([`62ed97c`](https://github.com/kalekundert/stepwise/commit/62ed97cd47608ba3c3e415a99b3fb016e57e52ea))
* Add the `reactions` builtin protocol ([`ccd2141`](https://github.com/kalekundert/stepwise/commit/ccd2141abde44a3db71727f52530313fb264f673))
* Add API for creating steps and substeps ([`89e7dbf`](https://github.com/kalekundert/stepwise/commit/89e7dbfd1748f30d1611175ab640560775bf2d55))

### Fix
* Return the error code instead of printing it ([`39a8934`](https://github.com/kalekundert/stepwise/commit/39a893409e4092fdf45006a10d04ae1e6b3fa847))

### Documentation
* Describe how to center-align table cells ([`117fb51`](https://github.com/kalekundert/stepwise/commit/117fb51c720801ae0699c888c4fd06447a025c00))
* Tweak wording ([`92cb3c6`](https://github.com/kalekundert/stepwise/commit/92cb3c6eac0d8208284289d4511bbccda9b06c94))
