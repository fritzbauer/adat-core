"""generate ADAT signals for simulation"""

from functools import reduce

def concatenate_lists(lists):
    """concatenate the elements of a list of lists"""
    return reduce(lambda a, b: a + b, lists)

class TestDataGenerator:
    """generate ADAT input data for simulation"""
    sync_sequence = 10 * [0]
    sync = [1]

    @staticmethod
    def postamble(userbits: list = None) -> list:
        """append sync bits and user bits"""
        if userbits is None:
            userbits = 4 * [0]
        return TestDataGenerator.sync + \
               TestDataGenerator.sync_sequence + \
               TestDataGenerator.sync + \
               userbits

    @staticmethod
    def chunks(lst: list, n: int):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    @staticmethod
    def convert_sample(sample24bit: int) -> list:
        """convert a 24 bit sample into an ADAT data bitstring"""
        bitstring = [ int(b) for b in concatenate_lists(
                        ['1' + s for s in
                            TestDataGenerator.chunks("{0:024b}".format(sample24bit), 4)])]
        print (bitstring)
        return bitstring

    @staticmethod
    def generate_adat_frame(sample_8channels: list) -> list:
        """converts an eight channel sample into an ADAT frame"""
        frame = concatenate_lists(
            [TestDataGenerator.convert_sample(sample_1ch) for sample_1ch in sample_8channels])
        frame.extend(TestDataGenerator.postamble())
        return frame

def generate_adat_frame(sample_8channels: list) -> list:
    """convenience method for converting an eight channel sample into an ADAT frame"""
    return TestDataGenerator.generate_adat_frame(sample_8channels)

def one_empty_adat_frame() -> list:
    """generate bits of one empty adat frame (all zero content)"""
    return generate_adat_frame(8 * [0])

def generate_one_frame_with_channel_numbers_as_samples() -> list:
    """return an ADAT frame whose samples are the channel numbers"""
    return generate_adat_frame(range(8))

def sixteen_frames_with_channel_num_msb_and_sample_num():
    """
       generate sixteen ADAT frames with channel numbers in the MSBs
       and sample numbers in the LSBs
    """
    samples_8ch = list(TestDataGenerator.chunks(
        [(channelno << 20 | sampleno)
            for sampleno in range(16)
            for channelno in range(8)
        ], 8))

    return concatenate_lists([generate_adat_frame(sample_8ch) for sample_8ch in samples_8ch])

def encode_nrzi(bits_in: list, initial_bit: int = 1) -> list:
    """NRZI-encode a list of bits"""
    result = [initial_bit]
    for bit in bits_in:
        last_bit = result[-1]
        result.append(last_bit if bit == 0 else (~last_bit) & 1)
    return result

if __name__ == "__main__":
    print(list(sixteen_frames_with_channel_num_msb_and_sample_num()))
