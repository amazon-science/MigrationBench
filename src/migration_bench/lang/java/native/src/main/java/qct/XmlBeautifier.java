package qct.ast_parser;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerException;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;

import org.w3c.dom.Document;
import org.xml.sax.SAXException;


public class XmlBeautifier {
    public static void main(String[] args) {
        try {
            // Load XML file
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document document = builder.parse(new File("input.xml"));

            // Write the modified document to file
            writeXmlToFile(document, "output.xml");
            
            System.out.println("XML file beautified successfully.");
        } catch (ParserConfigurationException | SAXException | IOException | TransformerException e) {
            e.printStackTrace();
        }
    }

    public static void writeXmlToFile(Document document, String fileName) throws TransformerException, IOException {
        // Create Transformer object for formatting
        TransformerFactory transformerFactory = TransformerFactory.newInstance();
        Transformer transformer = transformerFactory.newTransformer();
        transformer.setOutputProperty(OutputKeys.INDENT, "yes");
        transformer.setOutputProperty("{http://xml.apache.org/xslt}indent-amount", "4");

        // Write the modified document to file
        DOMSource source = new DOMSource(document);
        try (FileOutputStream fos = new FileOutputStream(fileName)) {
            StreamResult result = new StreamResult(fos);
            transformer.transform(source, result);
        }
    }
}
