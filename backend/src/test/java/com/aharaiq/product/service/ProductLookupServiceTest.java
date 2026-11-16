package com.aharaiq.product.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.aharaiq.product.exception.InvalidBarcodeException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class ProductLookupServiceTest {
    private RestTemplate restTemplate;
    private MockRestServiceServer server;
    private ProductLookupService service;

    @BeforeEach
    void setUp() {
        restTemplate = new RestTemplate();
        server = MockRestServiceServer.bindTo(restTemplate).build();
        service = new ProductLookupService(restTemplate, new ObjectMapper());
    }

    @Test
    void mapsAvailableOpenFoodFactsFields() {
        server.expect(requestTo("https://world.openfoodfacts.org/api/v2/product/8901234567890.json"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withStatus(HttpStatus.OK).body("""
                    {
                      "status": 1,
                      "product": {
                        "product_name": "Test Biscuits",
                        "brands": "Test Brand",
                        "categories": "Biscuits",
                        "image_front_url": "https://example.test/image.jpg",
                        "ingredients_text": "Wheat flour, sugar",
                        "nutriments": {
                          "energy-kcal_100g": 472,
                          "proteins_100g": 7.4,
                          "sugars_100g": 18.6
                        }
                      }
                    }
                    """));

        var result = service.lookup("8901234567890");

        assertThat(result.found()).isTrue();
        assertThat(result.name()).isEqualTo("Test Biscuits");
        assertThat(result.nutritionFacts()).extracting("field")
                .containsExactly("energy", "protein", "total_sugars");
        assertThat(result.missingFields()).contains("added_sugars");
        server.verify();
    }

    @Test
    void returnsNotFoundWithoutInventingProductData() {
        server.expect(requestTo("https://world.openfoodfacts.org/api/v2/product/0000000000000.json"))
                .andRespond(withStatus(HttpStatus.OK).body("{\"status\": 0}"));

        var result = service.lookup("0000000000000");

        assertThat(result.found()).isFalse();
        assertThat(result.name()).isNull();
        assertThat(result.nutritionFacts()).isEmpty();
    }

    @Test
    void rejectsInvalidBarcode() {
        assertThatThrownBy(() -> service.lookup("abc"))
                .isInstanceOf(InvalidBarcodeException.class);
    }

    @Test
    void mapsExternalFailureToLookupException() {
        server.expect(requestTo("https://world.openfoodfacts.org/api/v2/product/8901234567890.json"))
                .andRespond(withStatus(HttpStatus.BAD_GATEWAY));

        assertThatThrownBy(() -> service.lookup("8901234567890"))
                .hasMessageContaining("Open Food Facts could not be reached");
    }
}
