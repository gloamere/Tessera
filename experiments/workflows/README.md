# Experimental Gloamere workflows

This directory contains unpublished candidates. It is intentionally outside
`plugins/gloamere-workflows`, the marketplace, and every release archive.

## Provenance and similarity review

The three candidates were rewritten for the 4.0 product contracts. Their only
repository predecessors were first introduced by Gloamere in commit `c19f22f`
under this repository's MIT license; no third-party source, copied notice, or
separate upstream dependency was found for those files.

The following screening compares each current `SKILL.md` with its predecessor
at `c19f22f`. Inputs are UTF-8 text normalized to lowercase and collapsed
whitespace. The sequence ratio is diagnostic context; the 12-character Jaccard
score is language-neutral and catches shared Chinese wording without relying on
word segmentation. This is a reproducible engineering screen, not a legal
opinion.

| Candidate | Predecessor SHA-256 | Current SHA-256 | Sequence ratio | 12-character Jaccard |
| --- | --- | --- | ---: | ---: |
| `gloamere-finance-ops` | `56a0bbb10bcc60cfa960eb960464dcdb14a79775d1d7d87f108f17713461402b` | `b548eaae0a5847348debf923d8a5ad42f6a79ee8ffaad6a7376ece618e0b00d0` | 0.2034 | 0.0164 |
| `gloamere-growth-loop` | `d3ab178d76cca07849946fa9b4db9bcf669ac90f697afd5d4a886774f7d0fe1c` | `21e88f8ac6218fda3cdf2f73993957d5c76e68b681c5037abc3c7b7f47081663` | 0.2831 | 0.0054 |
| `gloamere-internal-ops` | `dfdd247ee0b20f6a717317ce2d9aa6b96f996aad77ad60a04f7a02255c2a5720` | `af5dc350d8fd215810a384620f38e365259c9849037553c7fe4902d21d99ebf2` | 0.5358 | 0.0389 |

The highest 12-character overlap is 3.89%; the longest shared normalized block
is 25 characters. Any content change invalidates these hashes and requires this
screen to be rerun.

## Graduation gate

A candidate remains unpublished until all of the following are true:

- its current SHA passes a fresh provenance, license, and similarity review;
- bilingual positive, adjacent-negative, and multi-intent routing cases pass
  the supported-version thresholds with three repeats in two independent task
  batches;
- at least five current-SHA quality tasks pass three repeats per condition with
  no significant regression;
- the workflow boundary, safety controls, and ownership are documented;
- adding it is accompanied by a `gloamere-workflows` version increase and a
  regenerated release manifest, marketplace, and release index.

Historical results and evidence from another Skill ID or SHA never satisfy this
gate.
