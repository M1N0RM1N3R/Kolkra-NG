# Contributing to `Kolkra-NG`

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

You can contribute in many ways:

# Types of Contributions

## Report Bugs

Report bugs at https://github.com/m1n0rm1n3r/Kolkra-NG/issues

If you are reporting a bug, please include detailed steps to reproduce the bug.

## Fix Bugs

Look through the GitHub issues for bugs.
Anything tagged with "bug" and "help wanted" is open to whoever wants to implement a fix for it.

## Implement Features

Look through the GitHub issues for features.
Anything tagged with "enhancement" and "help wanted" is open to whoever wants to implement it.

## Submit Feedback

The best way to send feedback is to file an issue at https://github.com/m1n0rm1n3r/Kolkra-NG/issues.

If you are proposing a new feature:

- Explain in detail how it would work.
- Keep the scope as narrow as possible, to make it easier to implement.
- Remember that this is a volunteer-driven project, and that contributions
  are welcome!

# Get Started!

Ready to contribute? Here's how to set up `Kolkra-NG` for local development.
Please note this documentation assumes you already have `poetry` and `Git` installed and ready to go.

1. Fork the `Kolkra-NG` repo on GitHub.

2. Clone your fork locally:

```bash
cd <directory_in_which_repo_should_be_created>
git clone git@github.com:YOUR_NAME/Kolkra-NG.git
```

3. Now we need to install the environment. Navigate into the directory

```bash
cd Kolkra-NG
```

If you are using `pyenv`, select a version to use locally. (See installed versions with `pyenv versions`)
(Kolkra-NG was built for Python 3.10 or later.)

```bash
pyenv local <x.y.z>
```

Then, install and activate the environment with:

```bash
poetry install
poetry shell
```

4. Install pre-commit to run various checks at commit time:

```bash
poetry run pre-commit install
```

5. Create a branch for local development:

```bash
git checkout -b name-of-your-bugfix-or-feature
```

Now you can make your changes locally.

6. When you're done making changes, check that your changes pass the linting checks.

```bash
make check
```

7. Test all features you added or changed in an isolated environment to help catch any bugs.

Create a configuration file at `config.toml`. `config.EXAMPLE.toml` provides a template and explanation for what fields you should provide.

You will also need to set up MongoDB, whether on your local machine or through a cloud provider like Atlas.
If you have Docker installed on your machine, you can quickly spin up an ephemeral MongoDB instance with an included Makefile script.

```bash
make start-mongo
```

8.  Commit your changes and push your branch to GitHub:

```bash
git add .
git commit -m "Your detailed description of your changes."
git push origin name-of-your-bugfix-or-feature
```

9. Submit a pull request through the GitHub website.

## Conventional Commits

Contributors are strongly encouraged, but not required, to follow [Conventional Commits](https://www.conventionalcommits.org/) in your commit messages.
If you use Visual Studio Code (or VSCodium), you should use the [Conventional Commits](https://marketplace.visualstudio.com/items?itemName=vivaxy.vscode-conventional-commits) extension to help you format your commit messages properly.
