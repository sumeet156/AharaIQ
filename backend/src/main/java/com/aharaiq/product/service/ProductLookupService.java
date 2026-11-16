package com.aharaiq.product.service;

import com.aharaiq.product.dto.NutritionFactResponse;
import com.aharaiq.product.dto.ProductLookupResponse;
import com.aharaiq.product.exception.InvalidBarcodeException;
import com.aharaiq.product.exception.ProductLookupException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

@Service
public class ProductLookupService {
    private static final Pattern BARCODE = Pattern.compile("\\d{8,14}");
    private static final String PRODUCT_URL =
            "https://world.openfoodfacts.org/api/v2/product/{barcode}.json";
    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public ProductLookupService(RestTemplate restTemplate, ObjectMapper objectMapper) {
        this.restTemplate = restTemplate;
        this.objectMapper = objectMapper;
    }

    public ProductLookupResponse lookup(String barcode) {
        if (barcode == null || !BARCODE.matcher(barcode.trim()).matches()) {
            throw new InvalidBarcodeException(barcode);
        }
        String normalizedBarcode = barcode.trim();
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("User-Agent", "AharaIQ/0.1 (academic food-label prototype)");
            ResponseEntity<String> response = restTemplate.exchange(
                    PRODUCT_URL,
                    HttpMethod.GET,
                    new HttpEntity<>(headers),
                    String.class,
                    normalizedBarcode);
            String payload = response.getBody();
            JsonNode root = objectMapper.readTree(payload);
            if (root.path("status").asInt(0) != 1 || root.path("product").isMissingNode()) {
                return notFound(normalizedBarcode);
            }
            return mapProduct(normalizedBarcode, root.path("product"));
        } catch (RestClientException | java.io.IOException exception) {
            throw new ProductLookupException("Open Food Facts could not be reached.", exception);
        }
    }

    private ProductLookupResponse mapProduct(String barcode, JsonNode product) {
        List<NutritionFactResponse> facts = new ArrayList<>();
        JsonNode nutrients = product.path("nutriments");
        addFact(facts, "energy", nutrients, "energy-kcal_100g", "kcal", "per_100_g");
        addFact(facts, "protein", nutrients, "proteins_100g", "g", "per_100_g");
        addFact(facts, "carbohydrates", nutrients, "carbohydrates_100g", "g", "per_100_g");
        addFact(facts, "total_sugars", nutrients, "sugars_100g", "g", "per_100_g");
        addFact(facts, "total_fat", nutrients, "fat_100g", "g", "per_100_g");
        addFact(facts, "saturated_fat", nutrients, "saturated-fat_100g", "g", "per_100_g");
        addFact(facts, "dietary_fibre", nutrients, "fiber_100g", "g", "per_100_g");
        addFact(facts, "sodium", nutrients, "sodium_100g", "g", "per_100_g");

        List<String> missing = new ArrayList<>();
        for (String field : List.of(
                "energy", "protein", "carbohydrates", "total_sugars",
                "added_sugars", "total_fat", "saturated_fat", "trans_fat",
                "dietary_fibre", "sodium")) {
            if (facts.stream().noneMatch(fact -> fact.field().equals(field))) {
                missing.add(field);
            }
        }
        return new ProductLookupResponse(
                true,
                barcode,
                text(product, "product_name"),
                text(product, "brands"),
                text(product, "categories"),
                text(product, "image_front_url"),
                text(product, "ingredients_text"),
                facts,
                missing,
                "Open Food Facts");
    }

    private void addFact(
            List<NutritionFactResponse> facts,
            String field,
            JsonNode nutrients,
            String key,
            String unit,
            String basis) {
        JsonNode value = nutrients.get(key);
        if (value != null && value.isNumber()) {
            facts.add(new NutritionFactResponse(field, value.asDouble(), unit, basis));
        }
    }

    private ProductLookupResponse notFound(String barcode) {
        return new ProductLookupResponse(
                false, barcode, null, null, null, null, null, List.of(), List.of(), "Open Food Facts");
    }

    private String text(JsonNode node, String field) {
        String value = node.path(field).asText(null);
        return value == null || value.isBlank() ? null : value;
    }
}
