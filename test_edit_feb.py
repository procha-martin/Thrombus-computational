from edit_feb import write_coeffs

write_coeffs(
    template_feb="Simple Shear Cube_120525_modelrun.feb",
    output_feb="tmp_test.feb",
    coeffs={
        "c1": 12.5,
        "c2": 1.1,
        "m1": 3.0,
        "m2": -0.5
    }
)

print("tmp_test.feb written successfully")
