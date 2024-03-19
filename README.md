# Kolkra-NG

[![Release](https://img.shields.io/github/v/release/m1n0rm1n3r/Kolkra-NG)](https://img.shields.io/github/v/release/m1n0rm1n3r/Kolkra-NG)
[![Build status](https://img.shields.io/github/actions/workflow/status/m1n0rm1n3r/Kolkra-NG/main.yml?branch=main)](https://github.com/m1n0rm1n3r/Kolkra-NG/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/m1n0rm1n3r/Kolkra-NG/branch/main/graph/badge.svg)](https://codecov.io/gh/m1n0rm1n3r/Kolkra-NG)
[![Commit activity](https://img.shields.io/github/commit-activity/m/m1n0rm1n3r/Kolkra-NG)](https://img.shields.io/github/commit-activity/m/m1n0rm1n3r/Kolkra-NG)
[![License](https://img.shields.io/github/license/m1n0rm1n3r/Kolkra-NG)](https://img.shields.io/github/license/m1n0rm1n3r/Kolkra-NG)

The next generation of Kolkra, the Splatfest server's custom utility bot.

- **Github repository**: <https://github.com/m1n0rm1n3r/Kolkra-NG/>
- **Documentation** <https://m1n0rm1n3r.github.io/Kolkra-NG/>

## Getting started with your project

First, create a repository on GitHub with the same name as this project, and then run the following commands:

```bash
git init -b main
git add .
git commit -m "init commit"
git remote add origin git@github.com:m1n0rm1n3r/Kolkra-NG.git
git push -u origin main
```

Finally, install the environment and the pre-commit hooks with

```bash
make install
```

You are now ready to start development on your project!
The CI/CD pipeline will be triggered when you open a pull request, merge to main, or when you create a new release.

To finalize the set-up for publishing to PyPi or Artifactory, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/publishing/#set-up-for-pypi).
For activating the automatic documentation with MkDocs, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/mkdocs/#enabling-the-documentation-on-github).
To enable the code coverage reports, see [here](https://fpgmaas.github.io/cookiecutter-poetry/features/codecov/).

## Releasing a new version

---

Repository initiated with [fpgmaas/cookiecutter-poetry](https://github.com/fpgmaas/cookiecutter-poetry).
