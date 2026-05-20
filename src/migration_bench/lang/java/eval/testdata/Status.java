package com.example;

/**
 * Top-level enum with constants whose bodies override an abstract method.
 * This shape (seen in repos like thomasmueller/tinyStats) previously crashed
 * parse_file.get_classes_and_methods because EnumDeclaration was not handled.
 */
public enum Status {
    OK {
        @Override
        public String describe() {
            return "ok";
        }
    },
    BAD {
        @Override
        public String describe() {
            return "bad";
        }
    };

    public abstract String describe();
}
