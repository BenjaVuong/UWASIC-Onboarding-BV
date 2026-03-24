/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_uwasic_onboarding_benjamin_vuong (

    assign uio_oe = 8'hFF;
    
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);


  // List all unused inputs to prevent warnings
  wire _unused = &{ena, ui_in[7:3], uio_in, clk, rst_n, 1'b0};

  localparam max_address = 7'h4;

  assign uio_oe = 8'hff;        // uio output mode i'm assuming

  wire SCLK_raw = ui_in[0];
  wire COPI_raw = ui_in[1];
  wire nCS_raw = ui_in[2];


  reg SCLK_mid_sync,  SCLK_sync,  SCLK_sync_prev;
  reg COPI_mid_sync,  COPI_sync,  COPI_sync_prev;
  reg nCS_mid_sync,   nCS_sync,   nCS_sync_prev;

  // Cleaning Up Metastability
  always@(posedge clk, negedge rst_n) begin
    if (!rst_n) begin
      // Reset behavior
      SCLK_mid_sync   <= 0;
      SCLK_sync       <= 0;
      SCLK_sync_prev  <= 0;
      COPI_mid_sync   <= 0;
      COPI_sync       <= 0;
      COPI_sync_prev  <= 0;
      nCS_mid_sync   <= 0;
      nCS_sync       <= 0;
      nCS_sync_prev  <= 0;
    end else begin
      // Normal Operation
      SCLK_mid_sync   <= SCLK_raw;
      SCLK_sync       <= SCLK_mid_sync;
      SCLK_sync_prev  <= SCLK_sync;
      COPI_mid_sync   <= COPI_raw;
      COPI_sync       <= COPI_mid_sync;
      COPI_sync_prev  <= COPI_sync;
      nCS_mid_sync    <= nCS_raw;
      nCS_sync        <= nCS_mid_sync;
      nCS_sync_prev   <= nCS_sync;
    end
  end




  reg [15:0] shift_reg;
  reg [4:0] bit_count;

  // Bit counting and shift register
  always@(posedge clk, negedge rst_n) begin
    if (!rst_n ) begin
      // Reset behavior
      shift_reg <= '0;
      bit_count <= '0;
    end else if (nCS_sync_prev && !nCS_sync) begin
      // New transaction behavior
      shift_reg <= '0;
      bit_count <= '0;
    end else if (!SCLK_sync_prev && SCLK_sync && (bit_count < 5'd16)) begin
      // Normal Operation
      bit_count <= bit_count + 1'b1;
      shift_reg[15:0] <= {shift_reg[14:0], COPI_sync};
    end
  end




  reg [7:0] en_reg_out_7_0, en_reg_out_15_8, en_reg_pwm_7_0, en_reg_pwm_15_8, pwm_duty_cycle;
  // Address Validation and Transaction Finalization
  always@(posedge clk, negedge rst_n) begin
    if (!rst_n) begin
      // Reset behavior
      en_reg_out_7_0[7:0]   <= 8'h0;
      en_reg_out_15_8[7:0]  <= 8'h0;
      en_reg_pwm_7_0[7:0]   <= 8'h0;
      en_reg_pwm_15_8[7:0]  <= 8'h0;
      pwm_duty_cycle[7:0]   <= 8'h0;
    end else if (!nCS_sync_prev && nCS_sync && (bit_count == 5'd16) && (shift_reg[15] == 1'b1) && (shift_reg[14:8] <= max_address)) begin
      // Normal Operation
      case (shift_reg[14:8]) 
        7'h0:
          en_reg_out_7_0[7:0]   <= shift_reg[7:0];
        7'h1:
          en_reg_out_15_8[7:0]  <= shift_reg[7:0];
        7'h2:
          en_reg_pwm_7_0[7:0]   <= shift_reg[7:0];
        7'h3:
          en_reg_pwm_15_8[7:0]  <= shift_reg[7:0];
        7'h4:
          pwm_duty_cycle[7:0]   <= shift_reg[7:0];
      endcase
    end
  end



  reg [12:0] pwm_step;
  // PWM Clock divider/Step counter
  always@(posedge clk, negedge rst_n) begin
    if (!rst_n) begin
      // Reset behavior
      pwm_step  <= 13'b0;
    end else if (pwm_step == 13'd3333) begin
      // Normal Operation
      pwm_step  <= '0;
    end else begin
      pwm_step  <= pwm_step + 13'b1;
    end
  end



  wire [12:0] pwm_duty_threshold = pwm_duty_cycle * 8'd13;
  reg pwm_signal;
  // PWM Signal threshold calculator
  always@(posedge clk, negedge rst_n) begin
    if (!rst_n) begin
      // Reset behavior
      pwm_signal <= 0;
    end else if (pwm_duty_cycle == 8'hFF) begin
      // Full Duty Cycle Operation
      pwm_signal <= 1'b1;
    end else if (pwm_step < pwm_duty_threshold) begin
      // Normal On Operation
      pwm_signal <= 1'b1;
    end else begin
      // Normal Off Operation
      pwm_signal <= 1'b0;
    end
  end


  assign uo_out   = en_reg_out_7_0 & (~en_reg_pwm_7_0 | {8{pwm_signal}});
  assign uio_out  = en_reg_out_15_8 & (~en_reg_pwm_15_8 | {8{pwm_signal}});



endmodule
