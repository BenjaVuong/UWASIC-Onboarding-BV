# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb.triggers import ClockCycles, with_timeout
from cocotb.types import Logic
from cocotb.types import LogicArray
from cocotb.utils import get_sim_time
from cocotb.result import SimTimeoutError

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def wait_rising_on_clk(sig, clk, timeout_ms=5):
    """
    Wait for a signal to rise.

    Params:
    - sig: the signal to be monitored
    - clk: module clock
    - timeout_ms: the time to wait until monitoring stopped
    """
    max_cycles = int(timeout_ms*10000)
    prev_val = sig.value

    for i in range(max_cycles):
        await RisingEdge(clk)
        current_val = sig.value

        if prev_val == 0 and current_val == 1:
            return True

        prev_val = current_val

    return False

async def wait_falling_on_clk(sig, clk, timeout_ms=5):
    """
    Wait for a signal to rise.

    Params:
    - sig: the signal to be monitored
    - clk: module clock
    - timeout_ms: the time to wait until monitoring stopped
    """
    max_cycles = int(timeout_ms*10000)
    prev_val = sig.value

    for i in range(max_cycles):
        await FallingEdge(clk)
        current_val = sig.value

        if prev_val == 1 and current_val == 0:
            return True

        prev_val = current_val

    return False

async def wait_high(sig, timeout_ms=5):
    """
    Wait for a signal to go high.

    Params:
    - sig: the signal to be monitored
    - clk: module clock
    - timeout_ms: the time to wait until monitoring stopped
    """
    max_cycles = int(timeout_ms*10000)

    for i in range(max_cycles):
        if(sig.value == 1):
            return True
        
    return False

async def wait_low(sig, timeout_ms=5):
    """
    Wait for a signal to go low.

    Params:
    - sig: the signal to be monitored
    - clk: module clock
    - timeout_ms: the time to wait until monitoring stopped
    """
    max_cycles = int(timeout_ms*10000)

    for i in range(max_cycles):
        if(sig.value == 0):
            return True
        
    return False

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")



@cocotb.test()
async def test_pwm_freq(dut):
    # Write your test here

    # 10 MHz clock
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset module
    dut._log.info("Testing Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    
    #   Enable output & pwm mode
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xff)
    #   Set the PWM cycle to 50%, enable outputs to PWM mode
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 127)
    

    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t1 = get_sim_time(units="ns")
    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t2 = get_sim_time(units="ns")

    pwm_period = (t2-t1)/1e9 #convert ns to seconds
    pwm_freq = 1/pwm_period

    assert 2970 < pwm_freq < 3030, f"PWM Freq supposed to be between 2970 and 3030, got {pwm_freq}"

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):
    # Write your test here


    # 10 MHz clock
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset module
    dut._log.info("Testing Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


    dut._log.info("PWM Test 0% Duty Cycle")
    #   Enable output & pwm mode
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xff)
    
    # Set the PWM cycle to 0%
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)
    # Make sure the signal doesn't turn on.
    assert await wait_rising_on_clk(dut.uo_out[0], dut.clk) == False, f"PWM signal rise detected, expected to stay off."

    # Set PWM cycle 50%
    dut._log.info("PWM Test 50% Duty Cycle")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 127)
    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t1_rise = get_sim_time(units="ns")
    await wait_falling_on_clk(dut.uo_out[0], dut.clk)
    t1_fall = get_sim_time(units="ns")
    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t2_rise = get_sim_time(units="ns")

    pwm_full_period = t2_rise - t1_rise
    pwm_high_period = (t1_fall - t1_rise)
    duty_cycle = pwm_high_period/pwm_full_period

    assert 0.48 < duty_cycle < 0.52, f"Duty cycle supposed to be between 48% and 52%, got {duty_cycle}"


    # Set PWM cycle 100%
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xff)
    assert await wait_falling_on_clk(dut.uo_out[0], dut.clk) == False, f"PWM signal fall detected, expected to stay on."

    
    # PWM Sweep test
    dut._log.info("PWM Sweep Test")
    for i in range (256):

        # Set PWM cycle to i
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, i)

        dut._log.info(f"PWM Sweep: {i}/255")
        if (i == 255):
            assert await wait_falling_on_clk(dut.uo_out[0], dut.clk) == False, f"PWM signal fall detected, expected to stay on."
        elif (i == 0):
            assert await wait_rising_on_clk(dut.uo_out[0], dut.clk) == False, f"PWM signal fall detected, expected to stay on."
        else: 
            await wait_rising_on_clk(dut.uo_out[0], dut.clk)
            t1_rise = get_sim_time(units="ns")
            await wait_falling_on_clk(dut.uo_out[0], dut.clk)
            t1_fall = get_sim_time(units="ns")
            await wait_rising_on_clk(dut.uo_out[0], dut.clk)
            t2_rise = get_sim_time(units="ns")

            ith_full_period = t2_rise - t1_rise
            ith_high_period = t1_fall - t1_rise
            ith_duty_cycle = ith_high_period/ith_full_period
            assert ((i/255) - 0.01) < ith_duty_cycle < ((i/255) + 0.01)


    # Output Enable + PWM Enable Reg Verification

    #   Set PWM cycle 50%
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 127)

    #   Test with output enable off
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0)
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xff)
    assert await wait_high(dut.uo_out[0]) == False, f"Signal on even when enable is on"

    #   Enable output, PWM mode off.
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x00)
    assert await wait_low(dut.uo_out[0]) == False, f"Signal is off, expected high"

    #   Enable output, PWM mode on.
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xff)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0xff)
    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t1_rise = get_sim_time(units="ns")
    await wait_falling_on_clk(dut.uo_out[0], dut.clk)
    t1_fall = get_sim_time(units="ns")
    await wait_rising_on_clk(dut.uo_out[0], dut.clk)
    t2_rise = get_sim_time(units="ns")

    pwm_full_period = t2_rise - t1_rise
    pwm_high_period = (t1_fall - t1_rise)
    duty_cycle = pwm_high_period/pwm_full_period

    assert 0.48 < duty_cycle < 0.52, f"Duty cycle supposed to be between 48% and 52%, got {duty_cycle}"
    

    

    dut._log.info("PWM Duty Cycle test completed successfully")
