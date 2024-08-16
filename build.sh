#!/bin/bash

name=ShKeeper
version=v2.0
folder=./ShKeeper

mkdir "./release"
mkdir "./release/$folder"
cp __init__.py "./release/$folder"
tar -a -c -f "./release/${name}_${version}.zip" "./release/$folder"
rm -r "./release/$folder"