# First citable research-prototype release

Version 0.1.0 is not yet a published release. Do not backdate publication or add
a DOI before one has actually been issued. A software release is not experimental
validation, peer review, or evidence that the cross-study admission gate is open.

## Publication checklist

1. Review and merge the numerical reproducibility fix only after all CI jobs pass.
2. Build wheel and sdist, install the wheel outside the checkout, and run the full
   suite in both explicitly tested pandas environments. Record the exact commit,
   Python/dependency versions and test results in release notes.
3. Independently resolve or explicitly list the known Sanglier unit-metadata
   limitation. Retain all admission blockers and private-data exclusions. Do not
   represent the archive as containing private source workbooks.
4. If a DOI is wanted, the account owner must connect and enable this repository
   in Zenodo before publishing the GitHub release. Inspect the archive and its
   attribution/licensing: MIT applies to code, not automatically to source data.
5. In a final reviewed commit, set the actual publication date in CITATION.cff
   and CHANGELOG.md and confirm version 0.1.0 matches pyproject.toml. Do not move
   an existing version tag; use a new version for later changes.
6. Tag that exact commit as v0.1.0 and publish a GitHub research-prototype release.
   State: retrospective batch benchmarks only; no prospective experimental
   result, cross-study validation or operational digital twin is established.
7. Verify Zenodo's issued version DOI and archived commit. Only then add the real
   DOI to the citation metadata in a follow-up commit. Never invent a DOI or imply
   that a later metadata commit was included in the previously archived release.

Publication requires explicit approval. Creating a release alone does not prove
numerical reproducibility; CI, input hashes and documented scientific scope remain
part of the evidence.
