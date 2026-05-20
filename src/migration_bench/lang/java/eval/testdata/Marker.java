package com.example;

/**
 * Top-level annotation declaration with a method element. Previously crashed
 * parse_file.get_classes_and_methods because AnnotationDeclaration was not
 * handled.
 */
public @interface Marker {
    String value() default "";
}
