package com.aharaiq.product.controller;

import com.aharaiq.product.dto.ProductLookupResponse;
import com.aharaiq.product.service.ProductLookupService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/products")
public class ProductController {
    private final ProductLookupService productLookupService;

    public ProductController(ProductLookupService productLookupService) {
        this.productLookupService = productLookupService;
    }

    @GetMapping("/{barcode}")
    public ProductLookupResponse lookup(@PathVariable String barcode) {
        return productLookupService.lookup(barcode);
    }
}
