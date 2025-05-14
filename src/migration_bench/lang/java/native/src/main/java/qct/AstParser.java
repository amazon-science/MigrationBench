/*
The binary to get the abstract syntax tree given a .java file.

Input:
  -input_files (str):       Full path to the .java file(s), supporting one single file now.
  -add_import (bool = false): Whether to parse imports.
  -add_line (bool = false): Whether to parse line numbers.
  -add_var (bool = false):  Whether to parse variables.

Output:
  -export_path (str):       Full path to the output xml file.
*/

package qct.ast_parser;


import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.ast.type.Type;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.HashMap;
import java.util.List;
import java.util.stream.Collectors;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.TransformerException;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.xml.sax.SAXException;

import qct.ast_parser.XmlBeautifier;


public class AstParser {

    public static void main(String[] args) throws FileNotFoundException {
        // Parse command-line arguments into a dictionary.
        HashMap<String, String> argMap = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--")) {
                // Argument in the format --name=value.
                String[] parts = args[i].substring(2).split("=", 2);
                argMap.put(parts[0], (parts.length > 1) ? parts[1] : "");
            } else if (args[i].startsWith("-")) {
                // Argument in the format -name value.
                String name = args[i].substring(1);
                String value = (i < args.length - 1 && !args[i + 1].startsWith("-")) ? args[i + 1] : "";
                argMap.put(name, value);
            }
        }

        String export_path = argMap.get("export_path");
        try {
            String input_files = argMap.get("input_files");
            System.out.printf("[QCT] Reading from `%s`.%n", input_files);

            // Parse the Java source file
            CompilationUnit cu = StaticJavaParser.parse(new File(input_files));

            // Create a DOM document to represent the XML structure
            DocumentBuilderFactory dbFactory = DocumentBuilderFactory.newInstance();
            DocumentBuilder dBuilder = dbFactory.newDocumentBuilder();
            Document doc = dBuilder.newDocument();

            // Create the root element
            Element rootElement = doc.createElement("root");
            doc.appendChild(rootElement);

            // Visit and export packages, imports, classes, and methods to XML
            new FileAnalyzerVisitor(
                doc, rootElement,
                Boolean.parseBoolean(argMap.getOrDefault("add_import", "false")),
                Boolean.parseBoolean(argMap.getOrDefault("add_line", "false")),
                Boolean.parseBoolean(argMap.getOrDefault("add_var", "false"))
            ).visit(cu, null);

            // Write the XML document to a file
            TransformerFactory transformerFactory = TransformerFactory.newInstance();
            Transformer transformer = transformerFactory.newTransformer();
            DOMSource source = new DOMSource(doc);

            System.out.printf("[QCT] Writing to `%s`.%n", export_path);
            StreamResult result = new StreamResult(new File(export_path));
            transformer.transform(source, result);

            System.out.println("[QCT] Done.");
        } catch (FileNotFoundException e) {
            e.printStackTrace();
        } catch (Exception e) {
            e.printStackTrace();
        }

        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            DocumentBuilder builder = factory.newDocumentBuilder();
            // Parse the XML file and create a Document object
            Document document = builder.parse(new File(export_path));
            // Document document = builder.parse(new ByteArrayInputStream(xmlBuilder.toString().getBytes()));

            // Write XML to file.
            PrintWriter out = new PrintWriter(export_path);
            XmlBeautifier.writeXmlToFile(document, export_path);
        } catch (ParserConfigurationException | SAXException | IOException | TransformerException e) {
            e.printStackTrace();
        }
    }

    // Visitor class to extract and export packages, imports, classes, and methods to XML
    private static class FileAnalyzerVisitor extends VoidVisitorAdapter<Void> {
        private final Document doc;
        private final Element rootElement;

        private boolean add_import;
        private boolean add_line;
        private boolean add_var;

        public FileAnalyzerVisitor(
            Document doc, Element rootElement,
            boolean add_import, boolean add_line, boolean add_var
        ) {
            this.doc = doc;
            this.rootElement = rootElement;

            this.add_import = add_import;
            this.add_line = add_line;
            this.add_var = add_var;
        }

        private Element addTag(Element rootElement, String field, String value) {
            Element nameElement = doc.createElement(field);
            rootElement.appendChild(nameElement);

            // Value
            if (!value.isEmpty()) {
                nameElement.setTextContent(value);
            }

            return nameElement;
        }

        private static String getClassDecSignature(ClassOrInterfaceDeclaration clsOrInterface) {
            StringBuilder signatureBuilder = new StringBuilder();

            // Append class or interface name
            signatureBuilder.append(String.join(" ",
                clsOrInterface.getAnnotations().stream()
                .map(AnnotationExpr::toString)
                .collect(Collectors.toList())
            ));

            String modifiers = clsOrInterface.getModifiers().stream()
                .map(modifier -> modifier.getKeyword().asString())
                .collect(Collectors.joining(" "));
            signatureBuilder.append(" ")
                .append(modifiers)
                .append(" class ")
                .append(clsOrInterface.getNameAsString());

            // Append extended classes
            List<String> extendedClasses = clsOrInterface.getExtendedTypes().stream()
                .map(ClassOrInterfaceType::getNameAsString)
                .collect(Collectors.toList());
            if (!extendedClasses.isEmpty()) {
                signatureBuilder.append(" extends ")
                    .append(String.join(", ", extendedClasses));
            }

            // Append implemented interfaces
            List<String> implementedInterfaces = clsOrInterface.getImplementedTypes().stream()
                .map(ClassOrInterfaceType::getNameAsString)
                .collect(Collectors.toList());
            if (!implementedInterfaces.isEmpty()) {
                signatureBuilder.append(" implements ")
                    .append(String.join(", ", implementedInterfaces));
            }

            return signatureBuilder.toString();
        }

        String getClassSignature(ClassOrInterfaceType clsOrInterface) {
            StringBuilder signatureBuilder = new StringBuilder();

            // Append the name of the parent class/interface
            signatureBuilder.append(clsOrInterface.getNameAsString());

            // If the parent has type parameters, append them to the signature
            NodeList<Type> typeArguments = clsOrInterface.getTypeArguments().orElse(NodeList.nodeList());
            if (!typeArguments.isEmpty()) {
                signatureBuilder.append("<");
                signatureBuilder.append(typeArguments.stream().map(Type::asString).collect(Collectors.joining(", ")));
                signatureBuilder.append(">");
            }

            return signatureBuilder.toString();
        }

        @Override
        public void visit(CompilationUnit cu, Void arg) {
            // Export package declaration to XML
            if (cu.getPackageDeclaration().isPresent()) {
                addTag(rootElement, "Package", cu.getPackageDeclaration().get().getNameAsString());
            }

            // Export import statements to XML
            if (add_import) {
                Element importsElement = addTag(rootElement, "Imports", "");
                cu.getImports().forEach(importDeclaration -> {
                    Element importElement = addTag(importsElement, "Import", "");

                    addTag(importElement, "Name", importDeclaration.getNameAsString());
                    if (add_line) {
                        addTag(importElement, "LineStart", String.valueOf(importDeclaration.getBegin().get().line));
                        addTag(importElement, "LineEnd", String.valueOf(importDeclaration.getEnd().get().line));
                    }
                });
            }

            super.visit(cu, arg);
        }

        @Override
        public void visit(ClassOrInterfaceDeclaration cls, Void arg) {
            // Export classes and methods to XML
            Element classElement = addTag(rootElement, "Class", "");

            // 0. Export name
            {
                addTag(classElement, "Name", cls.getNameAsString());
                addTag(classElement, "Signature", getClassDecSignature(cls));
                if (add_line) {
                    addTag(classElement, "LineStart", String.valueOf(cls.getBegin().get().line));
                    addTag(classElement, "LineEnd", String.valueOf(cls.getEnd().get().line));
                }
            }

            // 1. Export parent classes/ interfaces
            Element parentsElement = addTag(classElement, "Parents", "");
            cls.getExtendedTypes().forEach(extendedType -> {
                Element parentElement = addTag(parentsElement, "Parent", "");
                addTag(parentElement, "Name", extendedType.getNameAsString());
                addTag(parentElement, "Signature", getClassSignature(extendedType));
                if (add_line) {
                    addTag(parentElement, "LineStart", String.valueOf(extendedType.getBegin().get().line));
                }
                extendedType.accept(this, arg);
            });
            cls.getImplementedTypes().forEach(implType -> {
                Element parentElement = addTag(parentsElement, "Parent", "");
                addTag(parentElement, "Name", implType.getNameAsString());
                addTag(parentElement, "Signature", getClassSignature(implType));
                if (add_line) {
                    addTag(parentElement, "LineStart", String.valueOf(implType.getBegin().get().line));
                }
                implType.accept(this, arg);
            });

            // 2. Export constructors
            Element constructorsElement = addTag(classElement, "Constructors", "");
            cls.getConstructors().forEach(constructor -> {
                Element constructorElement = addTag(constructorsElement, "Constructor", "");

                addTag(constructorElement, "Name", constructor.getName().asString());
                addTag(constructorElement, "Signature", constructor.getDeclarationAsString());
                if (add_line) {
                    addTag(constructorElement, "LineStart", String.valueOf(constructor.getBegin().get().line));
                    addTag(constructorElement, "LineEnd", String.valueOf(constructor.getEnd().get().line));
                }
            });

            // 3. Export methods
            Element methodsElement = addTag(classElement, "Methods", "");
            cls.getMethods().forEach(method -> {
                Element methodElement = addTag(methodsElement, "Method", "");

                addTag(methodElement, "Name", method.getNameAsString());
                String methodDeclaration = method.getAnnotations().stream()
                    .map(AnnotationExpr::toString).collect(Collectors.joining(" ")) + " "
                    + method.getDeclarationAsString();
                addTag(methodElement, "Signature", methodDeclaration);
                addTag(
                    methodElement, "Override",
                    String.valueOf(method.getAnnotationByClass(Override.class).isPresent())
                );
                if (add_line) {
                    addTag(methodElement, "LineStart", String.valueOf(method.getBegin().get().line));
                    addTag(methodElement, "LineEnd", String.valueOf(method.getEnd().get().line));
                }

                if (add_var) {
                    Element paramsElement = addTag(methodElement, "Parameters", "");
                    method.getParameters().forEach(param -> {
                        Element paramElement = addTag(paramsElement, "Parameter", "");

                        String name = param.getName().asString();
                        String type = param.getType().asString();
                        addTag(paramElement, "Type", type);
                        addTag(paramElement, "Name", name);
                        addTag(paramElement, "Signature", type + " " + name);

                        if (add_line) {
                            addTag(paramElement, "LineStart", String.valueOf(param.getBegin().get().line));
                            addTag(paramElement, "LineEnd", String.valueOf(param.getEnd().get().line));
                        }
                    });

                    // Visit variable declarations inside the method
                    Element variablesElement = addTag(methodElement, "Variables", "");
                    method.findAll(VariableDeclarator.class).forEach(variable -> {
                        Element variableElement = addTag(variablesElement, "Variable", "");

                        String name = variable.getName().asString();
                        String type = variable.getType().asString();
                        addTag(variableElement, "Type", type);
                        addTag(variableElement, "Name", name);
                        addTag(variableElement, "Signature", type + " " + name);

                        if (add_line) {
                            addTag(variableElement, "LineStart", String.valueOf(variable.getBegin().get().line));
                            addTag(variableElement, "LineEnd", String.valueOf(variable.getEnd().get().line));
                        }
                    });
                }
            });

            // 4. Export properties
            if (add_var) {
                Element propertiesElement = addTag(classElement, "Properties", "");
                cls.getFields().forEach(field -> {
                    Element propertyElement = addTag(propertiesElement, "Property", "");

                    String name = field.getVariable(0).getNameAsString();
                    addTag(propertyElement, "Name", name);
                    addTag(propertyElement, "Type", field.getVariable(0).getType().toString());
                    addTag(propertyElement, "Signature", field.toString());

                    if (add_line) {
                        addTag(propertyElement, "LineStart", String.valueOf(field.getVariable(0).getBegin().get().line));
                        addTag(propertyElement, "LineEnd", String.valueOf(field.getVariable(0).getEnd().get().line));
                    }
                });
            }

            super.visit(cls, arg);
        }
    }
}
