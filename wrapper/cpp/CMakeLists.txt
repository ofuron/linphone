cmake_minimum_required(VERSION 3.6)

project(liblinphone++ LANGUAGES CXX)

add_library(linphone++
	src/account_creator.cc
)

include_directories(include/ ../../)
