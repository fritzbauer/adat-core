#!/usr/bin/env python3
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: CERN-OHL-W-2.0
#
""" ADAT transmitter.
    Inputs are in the sync clock domain,
    ADAT output is in the ADAT clock domain
"""

from amaranth          import Elaboratable, Signal, Module, Cat, Const, Array, signed
from amaranth.lib.fifo import AsyncFIFO

from amlib.utils import NRZIEncoder

class ADATTransmitterOwn(Elaboratable):
    """transmit ADAT from a multiplexed stream of eight audio channels

    Parameters
    ----------
    fifo_depth: capacity of the FIFO containing the ADAT frames to be transmitted

    Attributes
    ----------
    adat_out: Signal
        the ADAT signal to be transmitted by the optical transmitter
    addr_in: Signal
        contains the ADAT channel number (0-7) of the current sample to be written
        into the currently assembled ADAT frame
    sample_in: Signal
        the 24 bit sample to be written into the channel slot given by addr_in
        in the currently assembled ADAT frame
    user_data_in: Signal
        the user data bits of the currently assembled frame. Will be committed,
        when ``last_in`` is strobed high
    valid_in: Signal
        commits the data at sample_in into the currently assembled frame,
        but only if ``ready_out`` is high
    ready_out: Signal
        outputs if there is space left in the transmit FIFO. It also will
        prevent any samples to be committed into the currently assembled ADAT frame
    last_in: Signal
        needs to be strobed when the last sample has been committed into the currently
        assembled ADAT frame. This will commit the entire frame (including ``user_bits``)
        into the transmit FIFO.
    fifo_level_out: Signal
        outputs the number of entries in the transmit FIFO
    underflow_out: Signal
        this underflow indicator will be strobed, when a new ADAT frame needs to be
        transmitted but the transmit FIFO is empty. In this case, the last
        ADAT frame will be transmitted again.
    """

    def __init__(self, fifo_depth=512):
        self._fifo_depth    = fifo_depth
        self.adat_out       = Signal()
        self.addr_in        = Signal(3)
        self.sample_in      = Signal(24)
        self.user_data_in   = Signal(4)
        self.valid_in       = Signal()
        self.ready_out      = Signal()
        self.last_in        = Signal()
        self.fifo_level_out = Signal(range(fifo_depth))
        self.underflow_out  = Signal()

    @staticmethod
    def chunks(lst: list, n: int):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def elaborate(self, platform) -> Module:
        m = Module()
        sync = m.d.sync
        adat = m.d.adat
        comb = m.d.comb


        m.submodules.transmit_fifo = transmit_fifo = AsyncFIFO(width=25, depth=self._fifo_depth, w_domain="sync", r_domain="adat")

        # needed for input processing
        user_bits = Signal(4)
        user_bits_set = Signal()

        # needed for output processing
        m.submodules.nrzi_encoder = nrzi_encoder = NRZIEncoder()
        transmitted_frame_bits = Array([Signal(name=f"frame_bit{b}") for b in range(30)])
        transmitted_frame = Cat(transmitted_frame_bits)
        transmit_counter = Signal(5)
        transmit_size = Signal(5)

        comb += [
            self.ready_out.eq(transmit_fifo.w_rdy),
            self.fifo_level_out.eq(transmit_fifo.w_level),
            self.adat_out.eq(nrzi_encoder.nrzi_out),
            nrzi_encoder.data_in.eq(transmitted_frame_bits[transmit_counter]),
            self.underflow_out.eq(0),
        ]

        # 4b/5b coding: Every 24 bit channel has 6 nibbles.
        # 1 bit before the sync pad and one bit before the user data nibble
        filler_bits = [Const(1, 1) for _ in range(7)]
        sync_pad = Const(0, 10)

        #
        #
        # Fill the Fifo in sync domain
        #
        #


        sync += [
           # user_bits.eq(0),
          #  user_bits_set.eq(0),
          transmit_fifo.w_en.eq(0) # make sure, w_en is only asserted when explicitly strobed
        ]

        with m.If(user_bits_set):
            sync += [
                transmit_fifo.w_data.eq((1 << 24) | user_bits), #TODO: reverse?
                transmit_fifo.w_en.eq(1)
            ]

            sync += user_bits_set.eq(0)
            comb += self.ready_out.eq(transmit_fifo.w_rdy)

        with m.Else():
            with m.If(self.valid_in): #& self.ready_out needed?
                sync += [
                    transmit_fifo.w_data.eq(self.sample_in),
                    transmit_fifo.w_en.eq(1)
                ]

                with m.If(self.last_in):
                    sync += [
                        user_bits_set.eq(1),
                        user_bits.eq(self.user_data_in)
                    ]
                    comb += self.ready_out.eq(0) #we can't process input on this cycle

        #
        #
        # Read the Fifo and send data in adat domain
        #
        #
        adat += [
            transmit_counter.eq(transmit_counter + 1),
            transmit_fifo.r_en.eq(0),
        ]

        # initialize transmit_size once
        with m.If(transmit_size == 0):
            adat += transmit_size.eq(30)

        with m.If(transmit_counter == (transmit_size - 1)):
            adat += transmit_counter.eq(0)
            with m.If(transmit_fifo.r_rdy):
                with m.If(transmit_fifo.r_data[24] == 0):
                    adat += [
                        transmit_size.eq(30),
                        #transmitted_frame.eq(Cat(1 + (transmit_fifo.r_data[:5] << 17))),
                        transmitted_frame.eq(Cat(zip(filler_bits, list(self.chunks(transmit_fifo.r_data[:25], 4))))),
                        transmit_fifo.r_en.eq(1)
                    ]
                with m.Else():
                    adat += [
                        transmit_size.eq(16),
                        transmitted_frame.eq(Cat(1 + (transmit_fifo.r_data[:5] << 11))),
                        #transmitted_frame.eq(Cat(zip(filler_bits, list(self.chunks(transmit_fifo.r_data[:25], 4))))),
                        #transmitted_frame.eq(0b1111),
                        transmit_fifo.r_en.eq(1)
                    ]
            with m.Else():
                comb += self.underflow_out.eq(1)

        return m
