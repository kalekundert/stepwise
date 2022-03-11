# Changelog

<!--next-version-placeholder-->

## v0.30.0 (2022-03-11)
### Feature
* Allow quantity values to be any Real type ([`a25074b`](https://github.com/kalekundert/stepwise/commit/a25074bf730dd0b0db235a03efe96afcf9480d4a))

## v0.29.1 (2021-11-24)
### Fix
* Print to the specified printer ([`77eea75`](https://github.com/kalekundert/stepwise/commit/77eea7574d0659a598e3d3eff8e7b05cf336ac8a))

## v0.29.0 (2021-11-11)
### Feature
* Accept "conc" column in MasterMix.from_text() ([`b2727e7`](https://github.com/kalekundert/stepwise/commit/b2727e73c7ffe21ab983e7e080dd199b0c673819))
* Show concentrations in reaction tables ([`4afca87`](https://github.com/kalekundert/stepwise/commit/4afca87177476a7d649cce12f63daff98583bef5))

## v0.28.0 (2021-10-30)
### Feature
* Copy reagents, ignore 0-volume reagents ([`10574e6`](https://github.com/kalekundert/stepwise/commit/10574e643e1967a7c46b3c71822d66618927eb86))

## v0.27.2 (2021-08-25)
### Fix
* Allow preset config layers to be any iterable ([`0fa087d`](https://github.com/kalekundert/stepwise/commit/0fa087d85adc7b490f468cc175fe0af2f0c1a640))
* Remove duplicate footnotes ([`6d84a33`](https://github.com/kalekundert/stepwise/commit/6d84a339ffa3901cd2fe844826782790d1b6ffdd))

## v0.27.1 (2021-08-10)
### Fix
* Correctly read from stdin when using stash peek/pop ([`a8bea7f`](https://github.com/kalekundert/stepwise/commit/a8bea7f5336be028160699371725d8e63b76aae7))
* Restore name attribute to printer class ([`e664486`](https://github.com/kalekundert/stepwise/commit/e6644867b78242748da57d1dcae4c1cb29db82df))
* Improve error messages ([`38a130e`](https://github.com/kalekundert/stepwise/commit/38a130ec10ede5ea4687fb6d74f22265a0c19db1))

## v0.27.0 (2021-06-28)
### Feature
* Consider quantities unequal to None ([`fea7d55`](https://github.com/kalekundert/stepwise/commit/fea7d55d658a3af69f03c26fef77ee3ebff6dcf7))
* Make the StepwiseConfig root key a positional argument ([`1998907`](https://github.com/kalekundert/stepwise/commit/19989071fd5399d4df256560b4e8fe4828e92d46))
* Sort plugins by priority ([`33dfc6b`](https://github.com/kalekundert/stepwise/commit/33dfc6bf8ad70692408d2da7a19415ec10f906f1))
* Don't namespace plugin config files ([`dac3bc2`](https://github.com/kalekundert/stepwise/commit/dac3bc2fdeb056491a609603eca740012cdde08a))

## v0.26.0 (2021-06-17)
### Feature
* Allow preset names to be reused ([`0ca56ed`](https://github.com/kalekundert/stepwise/commit/0ca56ed27568288f56fa7c04da7d4f578eaf20fe))

## v0.25.0 (2021-05-28)
### Feature
* Add the testing submodule ([`4e5a280`](https://github.com/kalekundert/stepwise/commit/4e5a280dbf4ff6f68512b3db4b2064a961d46b47))
* Add Quantity.from_string_or_float() ([`d44aa42`](https://github.com/kalekundert/stepwise/commit/d44aa4261ad7c0b973b32237459b81d7535de948))
* Let the user fully specify how reactions are introduced ([`f23624a`](https://github.com/kalekundert/stepwise/commit/f23624ad0ee1d8dbb8ef27e6e289cd6132a1c343))

### Fix
* Don't share presets between instances ([`b074db7`](https://github.com/kalekundert/stepwise/commit/b074db73563ac0176f3536b2132f9cb20fe1b211))
* Don't show master mixes with only 1 reagent ([`acd5221`](https://github.com/kalekundert/stepwise/commit/acd52219f23ecd3c8c4c59b5e50ca4fd60c7b6ea))

## v0.24.0 (2021-05-05)
### Feature
* Allow negative reagent orders ([`dba0664`](https://github.com/kalekundert/stepwise/commit/dba066412cb472001075475ed997564c7d6fb12c))

## v0.23.0 (2021-04-30)
### Feature
* Add an Oxford comma function ([`1fc4b07`](https://github.com/kalekundert/stepwise/commit/1fc4b072cfd988afc7dee19031893271077356d3))

## v0.22.0 (2021-04-29)
### Feature
* Make Quantity a subclass of Real ([`3e91ecc`](https://github.com/kalekundert/stepwise/commit/3e91ecc9fe621d93f147b1ecc9e8d6b8b3d5383b))

## v0.21.2 (2021-04-28)
### Fix
* Report errors that occur when pickling protocols ([`df03481`](https://github.com/kalekundert/stepwise/commit/df034812e31d9b6798557c55cd1faca6567fb3e7))

## v0.21.1 (2021-04-27)
### Fix
* Allow the current working directory to change ([`7dc96ff`](https://github.com/kalekundert/stepwise/commit/7dc96ff7681e1dc9c7ad459befb54ce3dcd23eb8))

## v0.21.0 (2021-04-26)
### Feature
* Implement MasterMix.copy() ([`19dd947`](https://github.com/kalekundert/stepwise/commit/19dd947565b4c7cb13564f4c9b450287222d1436))
* Provide default width for formatting protocols ([`a52fb68`](https://github.com/kalekundert/stepwise/commit/a52fb6882d2964fc05aebea8c9af794687b67629))
* Expose config paths to protocol apps ([`7c386e3`](https://github.com/kalekundert/stepwise/commit/7c386e3491f540e8daff3f79d70be83ffed1743d))

### Fix
* Add missing import ([`ed4528b`](https://github.com/kalekundert/stepwise/commit/ed4528b971a01d8ff6252823dc01b75624110482))

## v0.20.0 (2021-04-06)
### Feature
* Add `Quantity.convert_unit()` ([`618d55e`](https://github.com/kalekundert/stepwise/commit/618d55ecbb8c6cc0f4b112328dc52cbb259aa8b9))

### Fix
* Allow `truncate_width` to be given ([`45d4608`](https://github.com/kalekundert/stepwise/commit/45d4608237dcefaaec6d5322954674aa0980aa62))

## v0.19.2 (2021-04-05)
### Fix
* Keep `dl` keys/values in sync after empty value ([`d562fe3`](https://github.com/kalekundert/stepwise/commit/d562fe3a7192acf5105e44d7e8e08188476acac2))

## v0.19.1 (2021-04-01)
### Fix
* Debug the `go` command ([`7285350`](https://github.com/kalekundert/stepwise/commit/7285350a043855983438fc41b2d529632ec944b3))
* Avoid infinite recursion with autoprop>=2.0 ([`bc6fdd8`](https://github.com/kalekundert/stepwise/commit/bc6fdd8bd63100d370a8a1791f81ec1148594b0d))
* Update semantics for callable `appcli.Layer` values ([`0a948bd`](https://github.com/kalekundert/stepwise/commit/0a948bd3b93bb17c522b3bcf2fc577c5b2c62904))

## v0.19.0 (2021-03-12)
### Feature
* Teach `sw step` about subsubsteps ([`fabfdd7`](https://github.com/kalekundert/stepwise/commit/fabfdd78a2e8477d67546f19541c4840c4d5f6f3))
* Add `dl` and `table` formatting objects ([`efb8a42`](https://github.com/kalekundert/stepwise/commit/efb8a42eda72fcf819ce04a9c1fb6c51830b3b06))

### Fix
* Remove more debugging code ([`e7533d1`](https://github.com/kalekundert/stepwise/commit/e7533d182f1f5b6856fd93db13c9cd7772674240))
* Remove debugging code ([`9891b1c`](https://github.com/kalekundert/stepwise/commit/9891b1cbd1432274111aa055663307536168a152))

## v0.18.0 (2021-03-09)
### Feature
* Gracefully handle unreadable stashed protocols ([`001003f`](https://github.com/kalekundert/stepwise/commit/001003f2288a46e7bda69685c5c486858cabaaf7))

## v0.17.1 (2021-03-08)
### Fix
* Address some formatting corner cases ([`9337bac`](https://github.com/kalekundert/stepwise/commit/9337bac7fd8e17cf1bc978a3e59fde1a6774a69d))

## v0.17.0 (2021-03-07)
### Feature
* Add better text formatting tools ([`bc8cb01`](https://github.com/kalekundert/stepwise/commit/bc8cb01f3a166d675022e155a241cb5db623fadf))
* Implement Reaction.iter_reagents_by_flag() ([`8261088`](https://github.com/kalekundert/stepwise/commit/8261088343962dfcc6155624cf105149303f7905))
* Allow `sw reaction` to eval volume arguments ([`33776cc`](https://github.com/kalekundert/stepwise/commit/33776cc8e577f5da174eeba89d18a43be14a1c31))
* Add options to the 'reaction' command ([`2638b5c`](https://github.com/kalekundert/stepwise/commit/2638b5cfbbbf2d7907de2e0777c56cd9406e4664))
* Provide method to simultaneously add and format footnotes ([`bbbd11a`](https://github.com/kalekundert/stepwise/commit/bbbd11a730629d10384d6d3621bc535a7234783d))
* Parse catalog numbers and flags for reaction tables ([`5c6dab3`](https://github.com/kalekundert/stepwise/commit/5c6dab357518b20750d6f1c74c982e41aec6268a))

## v0.16.0 (2021-01-20)
### Feature
* Make reaction tables less whitespace-sensitive ([`7f10b67`](https://github.com/kalekundert/stepwise/commit/7f10b6705e9ef4be11f0aff9bb79a4cfb5bc2011))

## v0.15.0 (2021-01-19)
### Feature
* Use a pager to display long protocols ([`b420f95`](https://github.com/kalekundert/stepwise/commit/b420f959ac41c0dd8057e6d6e8d84c64c6709415))

## v0.14.0 (2021-01-18)
### Feature
* Rename 'reactions' built-in command to 'conditions' ([`4f9ad51`](https://github.com/kalekundert/stepwise/commit/4f9ad512759226aaca767c3b51e7518be3c2941d))

## v0.13.0 (2021-01-18)
### Feature
* Add the 'reaction' built-in command ([`e107d78`](https://github.com/kalekundert/stepwise/commit/e107d78e02213c2eb0d7d8a70a8861052c5cc216))

## v0.12.0 (2021-01-15)
### Feature
* Implement Reaction.get_free_volume_excluding() ([`7d55fab`](https://github.com/kalekundert/stepwise/commit/7d55fab87de4774a807f20477e5e6dab854d630c))

### Fix
* Format subcommands briefs correctly ([`1dc4ca3`](https://github.com/kalekundert/stepwise/commit/1dc4ca3e2c9021942e933340e3b290fa58255a53))

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
