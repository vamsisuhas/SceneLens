load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Search engine library
py_library(
    name = "search",
    srcs = ["search.py"],
    deps = ["//pipeline:core"],
)

# FastAPI application library  
py_library(
    name = "api",
    srcs = ["app.py"],
        deps = [
        ":search", 
        "//pipeline:core",
    ],
)

# FastAPI server binary
py_binary(
    name = "server",
    srcs = ["app.py"],
    main = "app.py",
    deps = [":api"],
)