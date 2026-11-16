package com.aharaiq.product.controller;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aharaiq.product.dto.ProductLookupResponse;
import com.aharaiq.product.service.ProductLookupService;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ProductController.class)
class ProductControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ProductLookupService service;

    @Test
    void returnsStructuredProductResponse() throws Exception {
        when(service.lookup("8901234567890")).thenReturn(
                new ProductLookupResponse(
                        true, "8901234567890", "Test Product", "Test Brand",
                        "Biscuits", null, "Wheat flour", List.of(), List.of(), "Open Food Facts"));

        mockMvc.perform(get("/api/products/8901234567890"))
                .andExpect(status().isOk());
    }

    @Test
    void returnsBadRequestForInvalidBarcode() throws Exception {
        when(service.lookup("bad")).thenThrow(new com.aharaiq.product.exception.InvalidBarcodeException("bad"));

        mockMvc.perform(get("/api/products/bad"))
                .andExpect(status().isBadRequest());
    }
}
