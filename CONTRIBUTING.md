# Contributor Guide

This Juju charm is open source ([Apache License 2.0][LICENSE]) and we actively seek
any community contributions for code, suggestions and documentation. This page details a
few notes, workflows and suggestions for how to make contributions most effective and
help us all build a better charm - please give them a read before working on any
contributions.

## Licensing

This charm has been created under the [Apache License 2.0][LICENSE], which will cover
any contributions you may make to this project. Please familiarise yourself with the
terms of the license.

Additionally, this charm uses the Harmony CLA agreement.  It’s the easiest way for you
to give us permission to use your contributions.  In effect, you’re giving us a license,
but you still own the copyright — so you retain the right to modify your code and use it
in other projects. Please [sign the CLA here][CLA] before making any contributions.

## Code of Conduct

We have adopted the Ubuntu Code of Conduct. You can read this in full [here][CoC].

## Contributing Code

To contribute code to this project, submit a pull request on GitHub.

## Testing

The Python operator framework includes a very nice harness for testing operator
behaviour without full deployment. The default Tox environment includes the lint and
unit tests:

```
tox
```

Integration tests require an existing controller, and can be run using the `integration`
Tox environment target:


```
tox -e integration
```


[LICENSE]: ./LICENSE
[CLA]: https://ubuntu.com/legal/contributors/agreement
[CoC]: https://ubuntu.com/community/code-of-conduct
