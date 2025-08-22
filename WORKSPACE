workspace(name = "scenelens")

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# Python rules compatible with Bazel 7 - using older stable version
http_archive(
    name = "rules_python",
    sha256 = "a5640fddd4beb03e8c1fde5ed7160c0ba6bd477e7d048661c30c06936a26fd63",
    strip_prefix = "rules_python-0.22.1",
    url = "https://github.com/bazelbuild/rules_python/releases/download/0.22.1/rules_python-0.22.1.tar.gz",
)

load("@rules_python//python:repositories.bzl", "py_repositories", "python_register_toolchains")

py_repositories()

python_register_toolchains(
    name = "python3_11",
    python_version = "3.11",
)