#!/bin/bash
echo "Verifying classes are compiled with Java 17..."

class_files=($(find . -type f -path "*/target/classes/*.class"))

if [[ ${#class_files[@]} -eq 0 ]]; then
    echo "ERROR: No .class files found."
    exit 1
fi

for classfile in "${class_files[@]}"; do
    version=$(javap -verbose "$classfile" | grep "major version: " | awk '{print $NF}')

    if [[ "$version" != "61" ]]; then
    echo "ERROR: $classfile is not compiled with Java 17"
    exit 1
    fi
done

echo "All classes are compiled with Java 17"
