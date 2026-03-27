/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input wire clk,
    input wire rst_n,
    input wire SCLK,
    input wire COPI,
    input wire nCS,
    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);


  localparam max_address = 7'h4;

  // Signal Sync ----------------------------------------
  reg SCLK_mid_sync,  SCLK_sync,  SCLK_sync_prev;
  reg COPI_mid_sync,  COPI_sync,  COPI_sync_prev;
  reg nCS_mid_sync,   nCS_sync,   nCS_sync_prev;

  wire SCLK_rise = !SCLK_sync_prev & SCLK_sync;
  wire nCS_rise = !nCS_sync_prev & nCS_sync;
  wire nCS_fall = nCS_sync_prev & !nCS_sync;

  // Data Shift -----------------------------------------
  reg [15:0] shift_reg;
  reg [4:0] bit_count;

  reg transaction_ready;
  reg transaction_complete;

  // Data validity --------------------------------------
  wire addr_valid = (shift_reg[14:8] <= max_address);
  wire spi_valid =  transaction_ready && transaction_complete 
                    && shift_reg[15] && addr_valid;


  always@(posedge clk, negedge rst_n) begin

    if (!rst_n) begin
    // Reset behavior -------------------------------
      SCLK_mid_sync   <= 1'b0;
      SCLK_sync       <= 1'b0;
      SCLK_sync_prev  <= 1'b0;
      COPI_mid_sync   <= 1'b0;
      COPI_sync       <= 1'b0;
      COPI_sync_prev  <= 1'b0;
      nCS_mid_sync   <= 1'b0;
      nCS_sync       <= 1'b0;
      nCS_sync_prev  <= 1'b0;

      shift_reg <= 16'h0000;
      bit_count <= 5'b00000;
      transaction_ready <= 1'b0;
      transaction_complete <= 1'b1;

      en_reg_out_7_0[7:0]   <= 8'h0;
      en_reg_out_15_8[7:0]  <= 8'h0;
      en_reg_pwm_7_0[7:0]   <= 8'h0;
      en_reg_pwm_15_8[7:0]  <= 8'h0;
      pwm_duty_cycle[7:0]   <= 8'h0;

    end else begin
    // Signal Sync -----------------------------------
      SCLK_mid_sync   <= SCLK;
      SCLK_sync       <= SCLK_mid_sync;
      SCLK_sync_prev  <= SCLK_sync;
      COPI_mid_sync   <= COPI;
      COPI_sync       <= COPI_mid_sync;
      COPI_sync_prev  <= COPI_sync;
      nCS_mid_sync    <= nCS;
      nCS_sync        <= nCS_mid_sync;
      nCS_sync_prev   <= nCS_sync;

    // Shifting in data ------------------------------
      // Start of transfer period
      if (nCS_fall) begin 
        shift_reg <= 16'h0;
        bit_count <= 5'b00000;
        transaction_ready <= 1'b0;
        transaction_complete <= 1'b1;
      end 
      // If nCS still low, shift in data on SCLK rising 
      if (!nCS_sync & SCLK_rise) begin
        bit_count <= bit_count + 1'b1;
        shift_reg[15:0] <= {shift_reg[14:0], COPI_sync};
      end
      // If nCS rises, end data transfer
      if (nCS_rise) begin 
        transaction_ready <= 1'b1;
        transaction_complete <= (bit_count == 5'd16);
      end

    // Putting data into registers -------------------
      if (spi_valid) begin
        case(shift_reg[14:8])
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
        default: ; // this doesn't happen since spi_valid would not be HIGH
        endcase

        // Data output over, reset to starting state
        transaction_complete <= 1'b0;
        transaction_ready    <= 1'b0;
      end

    end
  end





endmodule
