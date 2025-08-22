load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(default_visibility = ["//visibility:public"])

# Streamlit UI library
py_library(
    name = "streamlit_app",
    srcs = ["app.py"],
)

# Streamlit UI binary
py_binary(
    name = "app",
    srcs = ["app.py"],
    main = "app.py",
    deps = [":streamlit_app"],
)