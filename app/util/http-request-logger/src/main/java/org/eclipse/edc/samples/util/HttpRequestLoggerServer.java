package org.eclipse.edc.samples.util;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

public class HttpRequestLoggerServer {

    static final String HTTP_PORT = "HTTP_SERVER_PORT";
    static String lastBody = "No data received yet.";

    public static void main(String[] args) {
        int port = Integer.parseInt(Optional.ofNullable(System.getenv(HTTP_PORT)).orElse("4000"));
        try {
            var server = HttpServer.create(new InetSocketAddress(port), 0);
            server.createContext("/", new ReceiverHandler());
            server.createContext("/data", new DataViewerHandler());
            server.setExecutor(null);
            server.start();
            System.out.println("HTTP request server logger started at port " + port);
        } catch (IOException e) {
            throw new RuntimeException("Unable to start server at port " + port, e);
        }
    }

    // Handler que guarda y muestra las peticiones entrantes
    private static class ReceiverHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            System.out.println("Incoming request");
            System.out.println("Method: " + exchange.getRequestMethod());
            System.out.println("Path: " + exchange.getRequestURI());

            BufferedReader reader = new BufferedReader(new InputStreamReader(exchange.getRequestBody(), StandardCharsets.UTF_8));
            StringBuilder body = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                body.append(line).append("\n");
            }

            lastBody = body.toString(); // guarda el último body recibido

            System.out.println("Body:");
            System.out.println(lastBody);
            System.out.println("=============");

            exchange.sendResponseHeaders(200, -1);
        }
    }

    // Handler para devolver el contenido en /data
    private static class DataViewerHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            byte[] responseBytes = lastBody.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "text/plain; charset=utf-8");
            exchange.sendResponseHeaders(200, responseBytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(responseBytes);
            }
        }
    }
}
